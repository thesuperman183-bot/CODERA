import { CodeReviewWorkspace } from "@/components/review/code-review-workspace";

export const metadata = {
  title: "Code Review Workspace | AI Code Review Agent",
  description: "Execute memory-guided AI code reviews with GitHub repository and Pull Request intelligence",
};

export default function CodeReviewPage() {
  return <CodeReviewWorkspace />;
}
