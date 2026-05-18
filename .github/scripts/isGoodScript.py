import subprocess
import re
import os
from openai import OpenAI

# ── Config ────────────────────────────────────────────────────────────────────

README_PATH = "README.md"

PROMPT_TEMPLATE = """
You are evaluating a job listing for a new grad software engineer.
Return only "GOOD" if it meets the criteria, or "BAD" if it does not. Be more generous than not.

Criteria:
- Must be more prestigious than Progressive Insurance Cloud Engineer. I am looking for a job that is a career booster.
- Does not necessarily have to FAANG companies although those are fine, I am looking for interesting roles working on interesting tech, at companies I can realistically expect to at least get an interview. A good example is Anduril.

Job listing:
{listing}
""".strip()

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_new_lines_since_commit(since_commit: str) -> list[str]:
    """Returns lines added to README.md since a given commit hash."""
    result = subprocess.run(
        ["git", "diff", since_commit, "HEAD", "--", README_PATH],
        capture_output=True, text=True
    )
    added_lines = []
    for line in result.stdout.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:].strip())
    return added_lines


def parse_job_listings(lines: list[str]) -> list[str]:
    """Extracts job listing rows from markdown table lines."""
    listings = []
    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            if re.search(r"[-]{3,}", line):  # skip divider rows
                continue
            clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', line)  # [text](url) -> text
            clean = re.sub(r'\s*\|\s*', ' | ', clean).strip('| ')
            if clean:
                listings.append(clean)
    return listings


def evaluate_listing(client: OpenAI, listing: str) -> bool:
    """Sends a listing to OpenAI and returns True if it passes."""
    prompt = PROMPT_TEMPLATE.format(listing=listing)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10,
        temperature=0,
    )
    verdict = response.choices[0].message.content.strip().upper()
    return verdict == "GOOD"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Use the commit hash saved before syncing upstream
    since_commit = os.environ.get("SINCE_COMMIT", "HEAD~20")
    print(f"Diffing README against commit: {since_commit}")

    new_lines = get_new_lines_since_commit(since_commit)

    if not new_lines:
        print("No new lines found in README since last run. Nothing to process.")
        return

    listings = parse_job_listings(new_lines)

    if not listings:
        print("No new job listing rows detected.")
        return

    print(f"Found {len(listings)} new listing(s). Evaluating with OpenAI...")

    passing = []
    for listing in listings:
        result = evaluate_listing(client, listing)
        status = "✅ GOOD" if result else "❌ BAD"
        print(f"{status}: {listing}")
        if result:
            passing.append(listing)

    print(f"\n── Summary ──────────────────────")
    print(f"{len(passing)}/{len(listings)} listings passed.")

    if passing:
        print("\nPassing listings:")
        for job in passing:
            print(f"  • {job}")
    else:
        print("No listings passed the filter.")


if __name__ == "__main__":
    main()