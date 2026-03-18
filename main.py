import argparse
import sys
import traceback

from agent.graph import agent

_MAX_RECURSION_LIMIT = 500


def main():
    parser = argparse.ArgumentParser(description="Run engineering project planner")
    parser.add_argument("--recursion-limit", "-r", type=int, default=100,
                        help="Recursion limit for processing (default: 100, max 500)")
    parser.add_argument("--debug", action="store_true",
                        help="Print full stack traces on error")

    args = parser.parse_args()

    recursion_limit = min(args.recursion_limit, _MAX_RECURSION_LIMIT)
    if recursion_limit != args.recursion_limit:
        print(f"Warning: recursion limit capped at {_MAX_RECURSION_LIMIT}", file=sys.stderr)

    try:
        user_prompt = input("Enter your project prompt: ")
        result = agent.invoke(
            {"user_prompt": user_prompt},
            {"recursion_limit": recursion_limit}
        )
        print("Final State:", result)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        if args.debug:
            traceback.print_exc()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
