"""Business logic service orchestrating code review processing and persistence in Neon."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.config import settings
from backend.models import (
    HindsightBank,
    RetainedFact,
    Review,
    ReviewFinding,
    ReviewMemory,
    Team,
    TeamRule,
    User,
)
from backend.schemas import FindingItem, RetainRequest, RetainResponse, ReviewRequest, ReviewResponse
from backend.services.finding_parser import parse_review_findings
from backend.services.groq_service import GroqService, groq_service
from backend.services.hindsight_service import HindsightMemoryService, hindsight_service


class CodeReviewProcessor:
    """Coordinates memory recall, team rules retrieval, LLM prompting, and Neon persistence."""

    def __init__(
        self,
        memory_service: Optional[HindsightMemoryService] = None,
        llm_service: Optional[GroqService] = None,
    ):
        self._memory_service = memory_service or hindsight_service
        self._llm_service = llm_service or groq_service
        self._in_memory_history: Dict[str, Dict[str, Any]] = {}

    async def _resolve_user_and_team(
        self,
        request: ReviewRequest,
        session: Optional[AsyncSession],
    ) -> tuple[Optional[str], Optional[str]]:
        """Identify user and team IDs, with database resolution when available."""
        user_id = request.user_id
        team_id = request.team_id

        if session is not None:
            # If user_id provided, verify existence
            if user_id:
                u_res = await session.execute(select(User.id).where(User.id == user_id))
                if not u_res.scalar_one_or_none():
                    user_id = None

            # If team_id provided, verify existence
            if team_id:
                t_res = await session.execute(select(Team.id).where(Team.id == team_id))
                if not t_res.scalar_one_or_none():
                    team_id = None

            # If not provided, fallback to the first active user and team if available
            if not user_id:
                first_user = (await session.execute(select(User.id).limit(1))).scalar_one_or_none()
                user_id = first_user

            if not team_id:
                first_team = (await session.execute(select(Team.id).limit(1))).scalar_one_or_none()
                team_id = first_team

        return user_id, team_id

    async def _resolve_hindsight_bank(
        self,
        user_id: Optional[str],
        team_id: Optional[str],
        session: Optional[AsyncSession],
    ) -> str:
        """Identify active Hindsight bank identifier from Neon or fallback settings."""
        if session is not None and (team_id or user_id):
            stmt = (
                select(HindsightBank.bank_id)
                .where(
                    HindsightBank.is_active == True,
                    (HindsightBank.team_id == team_id) | (HindsightBank.user_id == user_id),
                )
                .limit(1)
            )
            bank_id = (await session.execute(stmt)).scalar_one_or_none()
            if bank_id:
                return bank_id

        return settings.hindsight_bank_id

    async def _retrieve_team_rules(
        self,
        team_id: Optional[str],
        session: Optional[AsyncSession],
    ) -> List[tuple[str, Optional[str]]]:
        """Fetch applicable team rules from Neon database: returns list of (rule_text, memory_id)."""
        if session is None:
            return []

        stmt = select(TeamRule.rule_text, TeamRule.hindsight_memory_id)
        if team_id:
            stmt = stmt.where((TeamRule.team_id == team_id) | (TeamRule.team_id.is_(None)))
        
        rows = (await session.execute(stmt)).all()
        return [(r[0], r[1]) for r in rows]

    async def process_review(
        self,
        request: ReviewRequest,
        session: Optional[AsyncSession] = None,
        top_k: int = 5,
    ) -> ReviewResponse:
        """Execute the full 10-step review pipeline with Neon persistence."""
        # 1. Identify authenticated user and team
        user_id, team_id = await self._resolve_user_and_team(request, session)

        # 2. Identify active Hindsight bank
        bank_id = await self._resolve_hindsight_bank(user_id, team_id, session)

        # 3. Recall relevant memories from Hindsight with graceful fallback
        memories = []
        try:
            memories = self._memory_service.recall(
                query=request.code_diff,
                top_k=top_k,
                bank_id=bank_id,
            )
        except Exception:
            # Fall back gracefully to Neon team rules if Hindsight is unreachable
            memories = []

        # 4. Retrieve applicable team rules from Neon
        team_rules_data = await self._retrieve_team_rules(team_id, session)
        team_rule_texts = [r[0] for r in team_rules_data]

        # 5. Generate review through Groq with combined memory and team rules
        review_text, model_used = self._llm_service.generate_review(
            code_diff=request.code_diff,
            memories=memories,
            team_rules=team_rule_texts,
        )

        # 6. Parse review findings
        findings_items = parse_review_findings(review_text)

        # 7, 8, 9. Save Review, Findings, and Retrieved Memories in Neon (source of truth)
        review_id = str(uuid.uuid4())
        created_at_dt = datetime.now(timezone.utc)

        if session is not None:
            # 7. Save review record with optional GitHub repository provenance
            db_review = Review(
                id=review_id,
                user_id=user_id,
                team_id=team_id,
                source=request.source or "CLI",
                repository=request.repository,
                commit_sha=request.commit_sha,
                pr_number=request.pr_number,
                file_path=request.file_path,
                code_diff=request.code_diff,
                review_result=review_text,
                model_used=model_used,
                status="completed",
                created_at=created_at_dt,
            )
            session.add(db_review)

            # 8. Save findings
            for f in findings_items:
                db_finding = ReviewFinding(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    title=f.title,
                    description=f.description,
                    severity=f.severity,
                    file_path=f.file_path,
                    line_number=f.line_number,
                    recommendation=f.recommendation,
                )
                session.add(db_finding)

            # 9. Save retrieved memory references
            all_memories_to_record = []
            for mem_text in memories:
                all_memories_to_record.append((None, mem_text, "hindsight_recall"))
            for r_text, r_mem_id in team_rules_data:
                all_memories_to_record.append((r_mem_id, r_text, "team_rule"))

            for h_id, mem_text, source_type in all_memories_to_record:
                db_mem = ReviewMemory(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    hindsight_memory_id=h_id,
                    memory_text=mem_text,
                    relevance_metadata={"source": source_type, "bank_id": bank_id},
                )
                session.add(db_mem)

            await session.commit()

        # Cache in memory for quick retrieval
        self._in_memory_history[review_id] = {
            "id": review_id,
            "code_diff": request.code_diff,
            "review": review_text,
            "memories_used": memories + team_rule_texts,
            "findings": [f.model_dump() for f in findings_items],
            "model_used": model_used,
            "created_at": created_at_dt.isoformat(),
            "status": "completed",
            "user_id": user_id,
            "team_id": team_id,
        }

        # 10. Return complete review response
        return ReviewResponse(
            review=review_text,
            memories_used=memories + team_rule_texts,
            review_id=review_id,
            findings=findings_items,
            user_id=user_id,
            team_id=team_id,
            model_used=model_used,
            status="completed",
            repository=request.repository,
            commit_sha=request.commit_sha,
            pr_number=request.pr_number,
            file_path=request.file_path,
        )

    async def retain_rule(
        self,
        request: RetainRequest,
        session: Optional[AsyncSession] = None,
    ) -> RetainResponse:
        """Retain a fact or rule into Hindsight and persist metadata in Neon."""
        # 1. Identify bank
        bank_id = settings.hindsight_bank_id
        if session is not None and (request.team_id or request.user_id):
            bank_stmt = select(HindsightBank.bank_id).where(
                HindsightBank.is_active == True,
                (HindsightBank.team_id == request.team_id) | (HindsightBank.user_id == request.user_id),
            ).limit(1)
            b_found = (await session.execute(bank_stmt)).scalar_one_or_none()
            if b_found:
                bank_id = b_found

        # 2. Retain in Hindsight and verify provider confirmation
        metadata = {
            "tags": request.tags,
            "team_id": request.team_id,
            "user_id": request.user_id,
        }
        hindsight_res = self._memory_service.retain(
            content=request.rule,
            metadata=metadata,
            bank_id=bank_id,
        )

        hindsight_memory_id = hindsight_res.get("document_id") or hindsight_res.get("id")
        if not isinstance(hindsight_memory_id, str):
            hindsight_memory_id = None

        rule_id = str(uuid.uuid4())

        # 3. Save metadata and avoid duplicate records in Neon
        if session is not None:
            # Check for existing rule with same text and team to avoid duplicates
            existing_rule_stmt = select(TeamRule).where(
                TeamRule.rule_text == request.rule,
                TeamRule.team_id == request.team_id if request.team_id else TeamRule.team_id.is_(None),
            )
            existing_rule = (await session.execute(existing_rule_stmt)).scalar_one_or_none()

            if existing_rule:
                existing_rule.hindsight_memory_id = hindsight_memory_id or existing_rule.hindsight_memory_id
                existing_rule.created_at = datetime.now(timezone.utc)
                rule_id = existing_rule.id
            else:
                new_rule = TeamRule(
                    id=rule_id,
                    team_id=request.team_id,
                    created_by=request.user_id,
                    rule_text=request.rule,
                    hindsight_memory_id=hindsight_memory_id,
                )
                session.add(new_rule)

            # Record in retained facts table
            existing_fact_stmt = select(RetainedFact).where(
                RetainedFact.content == request.rule,
                RetainedFact.team_id == request.team_id if request.team_id else RetainedFact.team_id.is_(None),
            )
            existing_fact = (await session.execute(existing_fact_stmt)).scalar_one_or_none()

            if existing_fact:
                existing_fact.hindsight_memory_id = hindsight_memory_id or existing_fact.hindsight_memory_id
                existing_fact.tags = request.tags
            else:
                new_fact = RetainedFact(
                    id=str(uuid.uuid4()),
                    team_id=request.team_id,
                    user_id=request.user_id,
                    content=request.rule,
                    hindsight_memory_id=hindsight_memory_id,
                    tags=request.tags,
                )
                session.add(new_fact)

            await session.commit()

        return RetainResponse(
            status="retained",
            memory_id=hindsight_memory_id,
            rule_id=rule_id,
            team_id=request.team_id,
        )

    async def get_review_history(
        self,
        session: Optional[AsyncSession] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return review history from Neon or in-memory fallback."""
        if session is not None:
            stmt = (
                select(Review)
                .options(selectinload(Review.findings), selectinload(Review.memories))
                .order_by(Review.created_at.desc())
                .limit(limit)
            )
            reviews = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "id": r.id,
                    "code_diff": r.code_diff,
                    "review": r.review_result,
                    "model_used": r.model_used,
                    "source": r.source,
                    "status": r.status,
                    "user_id": r.user_id,
                    "team_id": r.team_id,
                    "created_at": r.created_at.isoformat(),
                    "findings_count": len(r.findings),
                    "memories_count": len(r.memories),
                }
                for r in reviews
            ]

        records = list(self._in_memory_history.values())
        records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return records[:limit]

    async def get_review_by_id(
        self,
        review_id: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve single review with findings and memories from Neon or memory."""
        if session is not None:
            stmt = (
                select(Review)
                .where(Review.id == review_id)
                .options(selectinload(Review.findings), selectinload(Review.memories))
            )
            r = (await session.execute(stmt)).scalar_one_or_none()
            if r:
                return {
                    "id": r.id,
                    "code_diff": r.code_diff,
                    "review": r.review_result,
                    "model_used": r.model_used,
                    "source": r.source,
                    "status": r.status,
                    "user_id": r.user_id,
                    "team_id": r.team_id,
                    "created_at": r.created_at.isoformat(),
                    "findings": [
                        {
                            "id": f.id,
                            "title": f.title,
                            "description": f.description,
                            "severity": f.severity,
                            "file_path": f.file_path,
                            "line_number": f.line_number,
                            "recommendation": f.recommendation,
                        }
                        for f in r.findings
                    ],
                    "memories": [
                        {
                            "id": m.id,
                            "memory_text": m.memory_text,
                            "hindsight_memory_id": m.hindsight_memory_id,
                            "relevance_metadata": m.relevance_metadata,
                        }
                        for m in r.memories
                    ],
                }

        return self._in_memory_history.get(review_id)

    @property
    def total_reviews_count(self) -> int:
        return len(self._in_memory_history)


review_processor = CodeReviewProcessor()
