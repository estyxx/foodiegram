"""Extraction History Tracking System

Tracks AI extraction improvements over time to help optimize prompts and models.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from foodiegram.types import Recipe


@dataclass
class ExtractionRun:
    """Represents a single extraction run."""

    run_id: str
    timestamp: datetime
    model_name: str
    processing_mode: str
    prompt_version: str
    total_posts: int
    successful_extractions: int
    average_confidence: float
    cost_estimate: float
    duration_seconds: float

    # Detailed metrics
    tag_counts: dict[str, int]
    confidence_distribution: dict[str, int]  # low, medium, high
    extraction_errors: list[str]

    # Prompt fingerprint for detecting changes
    prompt_fingerprint: str

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        return (
            (self.successful_extractions / self.total_posts) * 100
            if self.total_posts > 0
            else 0
        )


class ExtractionComparison(BaseModel):
    """Comparison between two extraction runs."""

    baseline_run: str
    comparison_run: str

    # Performance improvements
    success_rate_change: float
    confidence_change: float
    cost_change: float
    duration_change: float

    # Tag improvements
    new_tags_found: list[str]
    improved_tag_counts: dict[str, int]

    # Overall assessment
    improvement_score: float
    recommendations: list[str]


class ExtractionHistoryManager:
    """Manages extraction history and comparisons."""

    def __init__(self, history_file: Path = Path("extraction_history.json")):
        self.history_file = history_file
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        self.runs: dict[str, ExtractionRun] = {}
        self.load_history()

    def load_history(self) -> None:
        """Load extraction history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file) as f:
                    data = json.load(f)

                for run_data in data.get("runs", []):
                    # Convert timestamp back to datetime
                    run_data["timestamp"] = datetime.fromisoformat(run_data["timestamp"])
                    run = ExtractionRun(**run_data)
                    self.runs[run.run_id] = run

            except Exception as e:
                print(f"Warning: Could not load extraction history: {e}")

    def save_history(self) -> None:
        """Save extraction history to file."""
        try:
            data = {
                "runs": [
                    {**asdict(run), "timestamp": run.timestamp.isoformat()}
                    for run in self.runs.values()
                ],
                "last_updated": datetime.now().isoformat(),
            }

            with open(self.history_file, "w") as f:
                json.dump(data, f, indent=2, default=str)

        except Exception as e:
            print(f"Warning: Could not save extraction history: {e}")

    def create_prompt_fingerprint(self, prompts: dict[str, str]) -> str:
        """Create a fingerprint for prompts to detect changes."""
        prompt_text = json.dumps(prompts, sort_keys=True)
        return hashlib.md5(prompt_text.encode()).hexdigest()[:12]

    def record_extraction_run(
        self,
        recipes: list[Recipe],
        model_name: str,
        processing_mode: str,
        prompts: dict[str, str],
        cost_estimate: float,
        duration_seconds: float,
        run_id: str | None = None,
    ) -> str:
        """Record a new extraction run."""
        # Generate run ID if not provided
        if not run_id:
            timestamp = datetime.now()
            run_id = f"run_{timestamp.strftime('%Y%m%d_%H%M%S')}"

        # Calculate metrics
        successful_recipes = [r for r in recipes if r.is_recipe]

        total_posts = len(recipes)
        successful_extractions = len(successful_recipes)
        average_confidence = (
            sum(r.confidence_score for r in recipes) / total_posts
            if total_posts > 0
            else 0
        )

        # Analyze tag usage
        tag_counts = self._calculate_tag_counts(successful_recipes)

        # Confidence distribution
        confidence_distribution = self._calculate_confidence_distribution(recipes)

        # Extract errors
        extraction_errors = [
            r.analysis_notes
            for r in recipes
            if r.analysis_notes and "failed" in r.analysis_notes.lower()
        ]

        # Create run record
        run = ExtractionRun(
            run_id=run_id,
            timestamp=datetime.now(),
            model_name=model_name,
            processing_mode=processing_mode,
            prompt_version=self.create_prompt_fingerprint(prompts),
            total_posts=total_posts,
            successful_extractions=successful_extractions,
            average_confidence=average_confidence,
            cost_estimate=cost_estimate,
            duration_seconds=duration_seconds,
            tag_counts=tag_counts,
            confidence_distribution=confidence_distribution,
            extraction_errors=extraction_errors[:10],  # Limit to 10 errors
            prompt_fingerprint=self.create_prompt_fingerprint(prompts),
        )

        # Store run
        self.runs[run_id] = run
        self.save_history()

        return run_id

    def _calculate_tag_counts(self, recipes: list[Recipe]) -> dict[str, int]:
        """Calculate tag usage statistics."""
        tag_counts = {}

        for recipe in recipes:
            # Count different types of tags
            for tag_type in [
                "proteins",
                "vegetables",
                "key_ingredients",
                "cooking_method",
                "equipment",
                "dietary_tags",
                "occasion_tags",
            ]:
                tags = getattr(recipe, tag_type, [])
                if tags:
                    for tag in tags:
                        key = f"{tag_type}:{tag}"
                        tag_counts[key] = tag_counts.get(key, 0) + 1

        return tag_counts

    def _calculate_confidence_distribution(
        self,
        recipes: list[Recipe],
    ) -> dict[str, int]:
        """Calculate confidence score distribution."""
        distribution = {"high": 0, "medium": 0, "low": 0}

        for recipe in recipes:
            if recipe.confidence_score > 0.8:
                distribution["high"] += 1
            elif recipe.confidence_score > 0.6:
                distribution["medium"] += 1
            else:
                distribution["low"] += 1

        return distribution

    def get_latest_runs(self, limit: int = 10) -> list[ExtractionRun]:
        """Get the most recent extraction runs."""
        return sorted(
            self.runs.values(),
            key=lambda x: x.timestamp,
            reverse=True,
        )[:limit]

    def compare_runs(
        self,
        baseline_run_id: str,
        comparison_run_id: str,
    ) -> ExtractionComparison:
        """Compare two extraction runs."""
        baseline = self.runs.get(baseline_run_id)
        comparison = self.runs.get(comparison_run_id)

        if not baseline or not comparison:
            raise ValueError("One or both run IDs not found")

        # Calculate changes
        success_rate_change = comparison.success_rate - baseline.success_rate
        confidence_change = comparison.average_confidence - baseline.average_confidence
        cost_change = comparison.cost_estimate - baseline.cost_estimate
        duration_change = comparison.duration_seconds - baseline.duration_seconds

        # Find new tags
        baseline_tags = set(baseline.tag_counts.keys())
        comparison_tags = set(comparison.tag_counts.keys())
        new_tags_found = list(comparison_tags - baseline_tags)

        # Improved tag counts
        improved_tag_counts = {}
        for tag in baseline_tags & comparison_tags:
            diff = comparison.tag_counts[tag] - baseline.tag_counts[tag]
            if diff > 0:
                improved_tag_counts[tag] = diff

        # Calculate improvement score
        improvement_score = self._calculate_improvement_score(
            success_rate_change,
            confidence_change,
            len(new_tags_found),
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            success_rate_change,
            confidence_change,
            new_tags_found,
            improved_tag_counts,
        )

        return ExtractionComparison(
            baseline_run=baseline_run_id,
            comparison_run=comparison_run_id,
            success_rate_change=success_rate_change,
            confidence_change=confidence_change,
            cost_change=cost_change,
            duration_change=duration_change,
            new_tags_found=new_tags_found,
            improved_tag_counts=improved_tag_counts,
            improvement_score=improvement_score,
            recommendations=recommendations,
        )

    def _calculate_improvement_score(
        self,
        success_rate_change: float,
        confidence_change: float,
        new_tags_count: int,
    ) -> float:
        """Calculate overall improvement score (0-100)."""
        # Weights for different factors
        success_weight = 0.4
        confidence_weight = 0.4
        tags_weight = 0.2

        # Normalize changes to 0-100 scale
        success_score = max(0, min(100, 50 + success_rate_change * 2))
        confidence_score = max(0, min(100, 50 + confidence_change * 100))
        tags_score = min(100, new_tags_count * 10)

        return (
            success_score * success_weight
            + confidence_score * confidence_weight
            + tags_score * tags_weight
        )

    def _generate_recommendations(
        self,
        success_rate_change: float,
        confidence_change: float,
        new_tags: list[str],
        improved_tags: dict[str, int],
    ) -> list[str]:
        """Generate recommendations based on comparison."""
        recommendations = []

        if success_rate_change > 5:
            recommendations.append(
                "✅ Great improvement in success rate! Current prompts are working well.",
            )
        elif success_rate_change < -5:
            recommendations.append(
                "⚠️ Success rate decreased. Consider reverting prompt changes.",
            )

        if confidence_change > 0.1:
            recommendations.append("✅ Confidence scores improved significantly!")
        elif confidence_change < -0.1:
            recommendations.append("⚠️ Confidence scores dropped. Review prompt clarity.")

        if len(new_tags) > 10:
            recommendations.append(
                f"🏷️ Found {len(new_tags)} new tags! Extraction is more comprehensive.",
            )
        elif len(new_tags) == 0:
            recommendations.append(
                "🏷️ No new tags found. Consider expanding extraction prompts.",
            )

        if improved_tags:
            top_improved = sorted(
                improved_tags.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3]
            improved_list = ", ".join([tag.split(":")[1] for tag, _ in top_improved])
            recommendations.append(f"📈 Improved extraction for: {improved_list}")

        if not recommendations:
            recommendations.append(
                "📊 Results are similar to baseline. Consider A/B testing different prompts.",
            )

        return recommendations

    def get_trend_analysis(self, days: int = 30) -> dict[str, Any]:
        """Analyze trends over the last N days."""
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)

        recent_runs = [run for run in self.runs.values() if run.timestamp >= cutoff_date]

        if not recent_runs:
            return {"error": "No runs found in the specified period"}

        # Sort by timestamp
        recent_runs.sort(key=lambda x: x.timestamp)

        # Calculate trends
        success_rates = [run.success_rate for run in recent_runs]
        confidences = [run.average_confidence for run in recent_runs]
        costs = [run.cost_estimate for run in recent_runs]

        return {
            "period_days": days,
            "total_runs": len(recent_runs),
            "success_rate_trend": {
                "start": success_rates[0] if success_rates else 0,
                "end": success_rates[-1] if success_rates else 0,
                "change": success_rates[-1] - success_rates[0]
                if len(success_rates) > 1
                else 0,
                "average": sum(success_rates) / len(success_rates)
                if success_rates
                else 0,
            },
            "confidence_trend": {
                "start": confidences[0] if confidences else 0,
                "end": confidences[-1] if confidences else 0,
                "change": confidences[-1] - confidences[0]
                if len(confidences) > 1
                else 0,
                "average": sum(confidences) / len(confidences) if confidences else 0,
            },
            "cost_trend": {
                "total": sum(costs),
                "average_per_run": sum(costs) / len(costs) if costs else 0,
                "trend": "increasing"
                if len(costs) > 1 and costs[-1] > costs[0]
                else "stable",
            },
            "most_recent_run": recent_runs[-1].run_id if recent_runs else None,
        }

    def export_history(self, output_file: Path) -> None:
        """Export full history to a detailed JSON file."""
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "total_runs": len(self.runs),
            "runs": [
                {
                    **asdict(run),
                    "timestamp": run.timestamp.isoformat(),
                    "success_rate": run.success_rate,
                }
                for run in sorted(self.runs.values(), key=lambda x: x.timestamp)
            ],
            "summary": {
                "best_success_rate": max(
                    (run.success_rate for run in self.runs.values()),
                    default=0,
                ),
                "best_confidence": max(
                    (run.average_confidence for run in self.runs.values()),
                    default=0,
                ),
                "total_cost": sum(run.cost_estimate for run in self.runs.values()),
                "unique_prompts": len(
                    set(run.prompt_fingerprint for run in self.runs.values()),
                ),
            },
        }

        with open(output_file, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        print(f"✅ History exported to {output_file}")


# =====================================
# CLI UTILITIES
# =====================================


def print_run_summary(run: ExtractionRun) -> None:
    """Print a formatted summary of an extraction run."""
    print(f"\n📊 Run: {run.run_id}")
    print(f"🕒 Date: {run.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🤖 Model: {run.model_name}")
    print(f"⚡ Mode: {run.processing_mode}")
    print(
        f"📈 Success Rate: {run.success_rate:.1f}% ({run.successful_extractions}/{run.total_posts})",
    )
    print(f"🎯 Avg Confidence: {run.average_confidence:.1f}%")
    print(f"💰 Cost: ${run.cost_estimate:.3f}")
    print(f"⏱️  Duration: {run.duration_seconds:.1f}s")

    if run.tag_counts:
        top_tags = sorted(run.tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        print(
            f"🏷️  Top Tags: {', '.join([tag.split(':')[1] for tag, count in top_tags])}",
        )


def print_comparison(comparison: ExtractionComparison) -> None:
    """Print a formatted comparison between two runs."""
    print(f"\n🔍 Comparison: {comparison.baseline_run} → {comparison.comparison_run}")
    print(f"📈 Success Rate: {comparison.success_rate_change:+.1f}%")
    print(f"🎯 Confidence: {comparison.confidence_change:+.1f}%")
    print(f"💰 Cost: ${comparison.cost_change:+.3f}")
    print(f"⏱️  Duration: {comparison.duration_change:+.1f}s")
    print(f"🏷️  New Tags: {len(comparison.new_tags_found)}")
    print(f"🎖️  Improvement Score: {comparison.improvement_score:.1f}/100")

    print("\n💡 Recommendations:")
    for rec in comparison.recommendations:
        print(f"   {rec}")


if __name__ == "__main__":
    # Example usage
    history = ExtractionHistoryManager()

    # Show recent runs
    recent = history.get_latest_runs(5)
    print(f"📈 Found {len(recent)} recent runs")

    for run in recent:
        print_run_summary(run)
