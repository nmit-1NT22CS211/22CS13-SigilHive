# analytics_cli.py
import argparse
import json
from enhanced_analytics import EnhancedAnalytics
from tabulate import tabulate


def main():
    parser = argparse.ArgumentParser(description="Honeypot Analytics CLI")
    parser.add_argument(
        "--report", action="store_true", help="Generate analytics report"
    )
    parser.add_argument(
        "--hours", type=int, default=24, help="Hours to analyze (default: 24)"
    )
    parser.add_argument("--session", type=str, help="Get timeline for specific session")
    parser.add_argument("--export", type=str, help="Export report to JSON file")
    parser.add_argument("--top-commands", type=int, help="Show top N commands")

    args = parser.parse_args()

    analytics = EnhancedAnalytics()

    if args.session:
        # Show session timeline
        timeline = analytics.get_session_timeline(args.session)
        print(f"\n=== Session Timeline: {args.session} ===\n")

        headers = ["Timestamp", "Command", "Intent", "Directory", "Success"]
        rows = [
            [
                t["timestamp"],
                t["command"][:50],
                t["intent"],
                t["directory"],
                "✓" if t["success"] else "✗",
            ]
            for t in timeline
        ]

        print(tabulate(rows, headers=headers, tablefmt="grid"))

    elif args.report:
        # Generate report
        report = analytics.generate_report(hours=args.hours)

        print(f"\n{'=' * 60}")
        print("Honeypot Analytics Report")
        print(f"  Period: {report['period']}")
        print(f"  Generated: {report['generated_at']}")
        print(f"{'=' * 60}\n")

        # Statistics
        print("📊 Statistics:")
        stats = report["statistics"]
        print(f"  Total Sessions: {stats['total_sessions']}")
        print(f"  Avg Commands/Session: {stats['avg_commands_per_session']}")
        print(f"  Avg Success Rate: {stats['avg_success_rate']}%")
        print(f"  Suspicious Activities: {stats['total_suspicious_activities']}")
        print()

        # Top Commands
        if report["top_commands"]:
            print("🔝 Top Commands:")
            for cmd, count in list(report["top_commands"].items())[:10]:
                print(f"  {cmd[:40]:40} {count:>5}")
            print()

        # Intent Distribution
        if report["intent_distribution"]:
            print("🎯 Intent Distribution:")
            for intent, count in report["intent_distribution"].items():
                print(f"  {intent:30} {count:>5}")
            print()

        # Skill Level Distribution
        if report["skill_level_distribution"]:
            print("🎓 Skill Level Distribution:")
            for skill, count in report["skill_level_distribution"].items():
                print(f"  {skill:30} {count:>5}")
            print()

        # Attack Patterns
        if report["attack_patterns"]:
            print("⚠️  Attack Patterns Detected:")
            for pattern in report["attack_patterns"]:
                print(f"  [{pattern['severity'].upper()}] {pattern['type']}")
                print(
                    f"    Session: {pattern['session_id']}, Count: {pattern['count']}"
                )
            print()

        # Recommendations
        if report["recommendations"]:
            print("💡 Recommendations:")
            for i, rec in enumerate(report["recommendations"], 1):
                print(f"  {i}. {rec}")
            print()

        # Export if requested
        if args.export:
            with open(args.export, "w") as f:
                json.dump(report, f, indent=2, default=str)
            print(f"✅ Report exported to: {args.export}")

    elif args.top_commands:
        # Show top commands only
        report = analytics.generate_report(hours=args.hours)
        print(f"\n=== Top {args.top_commands} Commands (Last {args.hours} hours) ===\n")

        headers = ["Rank", "Command", "Count"]
        rows = [
            [i + 1, cmd, count]
            for i, (cmd, count) in enumerate(
                list(report["top_commands"].items())[: args.top_commands]
            )
        ]

        print(tabulate(rows, headers=headers, tablefmt="grid"))

    else:
        parser.print_help()

    analytics.close()


if __name__ == "__main__":
    main()
