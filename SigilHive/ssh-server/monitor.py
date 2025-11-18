# monitor.py - Real-time monitoring dashboard
import asyncio
import os
from datetime import datetime
from enhanced_analytics import EnhancedAnalytics


async def monitor_dashboard():
    """Real-time monitoring dashboard"""

    analytics = EnhancedAnalytics()

    while True:
        os.system("clear" if os.name != "nt" else "cls")

        print("=" * 70)
        print("  🍯 SSH HONEYPOT MONITORING DASHBOARD")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()

        # Get last 1 hour stats
        report = analytics.generate_report(hours=1)
        stats = report["statistics"]

        print("📊 LAST HOUR ACTIVITY:")
        print(f"   Sessions: {stats['total_sessions']}")
        print(f"   Avg Commands/Session: {stats['avg_commands_per_session']}")
        print(f"   Success Rate: {stats['avg_success_rate']}%")
        print(f"   🚨 Suspicious Activities: {stats['total_suspicious_activities']}")
        print()

        # Recent commands
        if report["top_commands"]:
            print("🔥 RECENT COMMANDS:")
            for cmd, count in list(report["top_commands"].items())[:5]:
                print(f"   {count:3}x  {cmd[:50]}")
            print()

        # Active intents
        if report["intent_distribution"]:
            print("🎯 ATTACKER INTENTS:")
            for intent, count in list(report["intent_distribution"].items())[:5]:
                print(f"   {count:3}x  {intent}")
            print()

        # Recent attack patterns
        if report["attack_patterns"]:
            print("⚠️  ATTACK PATTERNS:")
            for pattern in report["attack_patterns"][:3]:
                severity_emoji = "🔴" if pattern["severity"] == "high" else "🟡"
                print(
                    f"   {severity_emoji} {pattern['type']} (Session: {pattern['session_id'][:8]})"
                )
            print()

        print("=" * 70)
        print("Press Ctrl+C to exit")

        await asyncio.sleep(5)  # Update every 5 seconds


if __name__ == "__main__":
    try:
        asyncio.run(monitor_dashboard())
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped")
