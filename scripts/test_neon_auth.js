/**
 * Demonstration and verification script for Neon Managed Better Auth.
 * Performs email and password registration, then signs in to verify user retrieval.
 */
const { createAuthClient } = require("@neon/auth");

const authUrl = process.env.NEON_AUTH_BASE_URL;
if (!authUrl) {
  console.error("NEON_AUTH_BASE_URL is not set in environment.");
  process.exit(1);
}

const client = createAuthClient(authUrl, {
  fetchOptions: {
    headers: {
      Origin: "http://localhost:3000",
    },
  },
});

async function main() {
  const uniqueId = Date.now();
  const testEmail = `developer_${uniqueId}@example.com`;
  const testPassword = "SecurePassword123!";
  const testName = "Neon Auth Verified User";

  console.log("=== 1. Signing up test user via Neon Auth ===");
  console.log("Target Email:", testEmail);

  const signUpResponse = await client.signUp.email({
    email: testEmail,
    password: testPassword,
    name: testName,
  });

  if (signUpResponse.error) {
    console.error("Sign up failed:", signUpResponse.error);
    process.exit(1);
  }

  const createdUser = signUpResponse.data?.user;
  console.log("Sign up successful!");
  console.log("User ID:", createdUser?.id);
  console.log("User Email:", createdUser?.email);
  console.log("User Name:", createdUser?.name);
  console.log("Created At:", createdUser?.createdAt);

  console.log("\n=== 2. Reading current user back with signIn.email ===");
  const signInResponse = await client.signIn.email({
    email: testEmail,
    password: testPassword,
  });

  if (signInResponse.error) {
    console.error("Sign in failed:", signInResponse.error);
    process.exit(1);
  }

  const verifiedUser = signInResponse.data?.user;
  console.log("Verified user session active!");
  console.log("Retrieved User ID:", verifiedUser?.id);
  console.log("Retrieved User Email:", verifiedUser?.email);
  console.log("Retrieved User Name:", verifiedUser?.name);
  console.log("\nSUCCESS: Neon Managed Better Auth email signup and retrieval verified!");
}

main().catch((err) => {
  console.error("Unexpected error:", err);
  process.exit(1);
});

