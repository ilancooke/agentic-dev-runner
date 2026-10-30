import json
import subprocess
import sys

REPOSITORY = "ilancooke/milestone-runner-test"
PR_NUMBER = 1
EXPECTED_CHECK = "test"


def gh_api(endpoint):
    result = subprocess.run(
        ["gh", "api", f"repos/{REPOSITORY}/{endpoint}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def main():
    pr = gh_api(f"pulls/{PR_NUMBER}")

    if pr["state"] != "open":
        sys.exit("FAIL: Pull request is not open.")

    if pr["base"]["ref"] != "main":
        sys.exit("FAIL: Unexpected target branch.")

    head_sha = pr["head"]["sha"]
    print(f"PR #{PR_NUMBER} head: {head_sha}")

    checks = gh_api(f"commits/{head_sha}/check-runs")
    matching = [
        check for check in checks["check_runs"]
        if check["name"] == EXPECTED_CHECK
        and check["head_sha"] == head_sha
        and check["app"]["slug"] == "github-actions"
    ]

    if len(matching) != 1:
        sys.exit(
            f"FAIL: Expected exactly one GitHub Actions "
            f"check named {EXPECTED_CHECK!r}; found {len(matching)}."
        )

    check = matching[0]
    print(f"Check: {check['name']}")
    print(f"Status: {check['status']}")
    print(f"Conclusion: {check['conclusion']}")

    if (
        check["status"] != "completed"
        or check["conclusion"] != "success"
    ):
        sys.exit("FAIL: Required CI check has not passed.")

    print("\nPASS: Required CI check succeeded for the exact PR head commit.")


if __name__ == "__main__":
    main()
