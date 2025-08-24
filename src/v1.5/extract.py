#!/usr/bin/env python3
"""Enhanced Recipe Extraction with Batch Processing Support

Usage:
    python extract.py --collection-id 123456789 --limit 100 --mode batch
    python extract.py --collection-id 123456789 --limit 50 --mode concurrent
    python extract.py --collection-id 123456789 --limit 200 --mode auto
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from instagrapi import Client
from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table
from rich.text import Text

from foodiegram import env
from foodiegram.analyzer import EnhancedRecipeAnalyzer, ProcessingMode
from foodiegram.types import Media, Recipe

console = Console()


class ProgressTracker:
    """Rich-based progress tracker for recipe analysis."""

    def __init__(self):
        self.progress = None
        self.task_id = None

    def start(self, description: str, total: int):
        """Start progress tracking."""
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        )
        self.progress.start()
        self.task_id = self.progress.add_task(description, total=total)

    def update(self, description: str, completed: int, total: int):
        """Update progress."""
        if self.progress and self.task_id is not None:
            self.progress.update(
                self.task_id,
                description=description,
                completed=completed,
                total=total,
            )

    def stop(self):
        """Stop progress tracking."""
        if self.progress:
            self.progress.stop()


class InstagramExtractor(BaseModel):
    """Enhanced Instagram extractor with caching."""

    _client: Client = None
    username: str
    password: str

    @property
    def client(self) -> Client:
        """Lazy load the Instagram client."""
        if getattr(self, "_client", None):
            return self._client

        self._client = Client()
        self._client.login(self.username, self.password)
        return self._client

    def extract_saved_posts(self, collection_id: int, limit: int = 10) -> list[Media]:
        """Extract saved posts from Instagram collection."""
        console.print(f"🔍 Extracting {limit} posts from collection {collection_id}")

        medias = self.client.collection_medias(collection_pk=collection_id, amount=limit)

        posts: list[Media] = []
        for media in medias:
            post = Media(
                pk=media.pk,
                id=media.id,
                code=media.code,
                taken_at=media.taken_at,
                caption_text=media.caption_text or "",
                thumbnail_url=media.thumbnail_url,
                title=media.title,
            )
            posts.append(post)

        console.print(f"✅ Successfully extracted {len(posts)} posts")
        return posts


def show_cost_estimate(analyzer: EnhancedRecipeAnalyzer, posts: list[Media], mode: str):
    """Display cost estimates for different processing modes."""
    console.print("\n💰 [bold]Cost Analysis[/bold]")

    # Get estimates for both modes
    if mode == ProcessingMode.AUTO:
        recommendation = analyzer.get_processing_recommendation(posts)

        table = Table(title="Processing Cost Comparison")
        table.add_column("Mode", style="cyan")
        table.add_column("Cost", justify="right", style="green")
        table.add_column("Time", style="yellow")
        table.add_column("Notes", style="dim")

        table.add_row(
            "Batch",
            f"${recommendation['batch_cost']:.3f}",
            "< 24 hours",
            "50% discount, async",
        )
        table.add_row(
            "Concurrent",
            f"${recommendation['concurrent_cost']:.3f}",
            "~5-10 minutes",
            "Standard rate, immediate",
        )

        console.print(table)

        savings_text = Text()
        savings_text.append("💡 Recommendation: ", style="bold")
        savings_text.append(f"Use {recommendation['recommended_mode']} mode\n")
        savings_text.append(
            f"Potential savings: ${recommendation['savings_amount']:.2f} ",
        )
        savings_text.append(
            f"({recommendation['savings_percentage']:.1f}%)",
            style="green bold",
        )

        console.print(Panel(savings_text, title="💡 Smart Recommendation"))

    else:
        estimate = analyzer.estimate_cost(posts, mode)

        table = Table(title=f"Cost Estimate - {mode.title()} Mode")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        table.add_row("Total Posts", str(estimate["total_posts"]))
        table.add_row("Estimated Requests", str(estimate["estimated_requests"]))
        table.add_row("Estimated Cost", f"${estimate['estimated_total_cost']:.3f}")
        table.add_row("Cost per Recipe", f"${estimate['cost_per_recipe']:.4f}")

        console.print(table)


def confirm_processing(mode: str, posts_count: int) -> bool:
    """Confirm processing with user."""
    if mode == ProcessingMode.BATCH:
        message = (
            f"🚀 Ready to process {posts_count} posts using [bold cyan]Batch mode[/bold cyan]\n"
            f"⏱️  Processing time: Up to 24 hours (often much faster)\n"
            f"💰 Cost savings: ~50% compared to concurrent processing\n"
            f"📊 Results: Will be available when batch completes"
        )
    else:
        message = (
            f"⚡ Ready to process {posts_count} posts using [bold yellow]Concurrent mode[/bold yellow]\n"
            f"⏱️  Processing time: ~{posts_count * 0.5 / 60:.1f} minutes\n"
            f"💰 Cost: Standard API rates\n"
            f"📊 Results: Available immediately"
        )

    console.print(Panel(message, title="🔍 Processing Confirmation"))

    try:
        response = input("\nProceed with analysis? [Y/n]: ").strip().lower()
        return response in ("", "y", "yes")
    except KeyboardInterrupt:
        console.print("\n❌ Processing cancelled by user")
        return False


def save_results(recipes: list[Recipe], output_file: Path) -> None:
    """Save analysis results to JSON file."""
    console.print(f"\n💾 Saving results to {output_file}")

    # Convert recipes to dict format for JSON serialization
    recipes_data = []
    for recipe in recipes:
        recipe_dict = recipe.model_dump()
        # Convert datetime and other non-serializable types to strings
        for key, value in recipe_dict.items():
            if hasattr(value, "isoformat"):  # datetime
                recipe_dict[key] = value.isoformat()
            elif hasattr(value, "value"):  # enum
                recipe_dict[key] = value.value

        recipes_data.append(recipe_dict)

    # Save with pretty formatting
    output_file.write_text(
        json.dumps(recipes_data, indent=2, default=str, ensure_ascii=False),
    )

    console.print("✅ Results saved successfully!")


def display_analysis_summary(recipes: list[Recipe]) -> None:
    """Display analysis summary."""
    total_recipes = len(recipes)
    successful_recipes = len([r for r in recipes if r.is_recipe])
    failed_recipes = len([r for r in recipes if not r.is_recipe])

    avg_confidence = (
        sum(r.confidence_score for r in recipes) / total_recipes
        if total_recipes > 0
        else 0
    )

    # Create summary table
    summary_table = Table(title="📊 Analysis Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", justify="right", style="green")

    summary_table.add_row("Total Posts Analyzed", str(total_recipes))
    summary_table.add_row("Recipes Found", str(successful_recipes))
    summary_table.add_row("Non-Recipes", str(failed_recipes))
    summary_table.add_row(
        "Success Rate",
        f"{(successful_recipes / total_recipes) * 100:.1f}%",
    )
    summary_table.add_row("Average Confidence", f"{avg_confidence * 100:.1f}%")

    console.print(summary_table)

    # Show top recipes by confidence
    if successful_recipes > 0:
        top_recipes = sorted(
            [r for r in recipes if r.is_recipe],
            key=lambda x: x.confidence_score,
            reverse=True,
        )[:5]

        console.print("\n🏆 [bold]Top Recipes by Confidence[/bold]")
        for i, recipe in enumerate(top_recipes, 1):
            confidence_color = (
                "green"
                if recipe.confidence_score > 0.8
                else "yellow"
                if recipe.confidence_score > 0.6
                else "red"
            )
            console.print(
                f"{i}. {recipe.title} "
                f"[{confidence_color}]({recipe.confidence_score * 100:.1f}%)[/{confidence_color}]",
            )


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Extract and analyze recipes from Instagram collections with AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--collection-id",
        type=int,
        required=True,
        help="Instagram collection ID to analyze",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of posts to analyze (default: 50)",
    )

    parser.add_argument(
        "--mode",
        choices=[ProcessingMode.BATCH, ProcessingMode.CONCURRENT, ProcessingMode.AUTO],
        default=ProcessingMode.AUTO,
        help="Processing mode: batch (50%% cheaper, up to 24h), concurrent (immediate), auto (smart choice)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("analyzed_recipes.json"),
        help="Output file for results (default: analyzed_recipes.json)",
    )

    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompts",
    )

    parser.add_argument(
        "--cache",
        action="store_true",
        default=True,
        help="Enable result caching (default: True)",
    )

    args = parser.parse_args()

    # Show banner
    console.print(
        Panel(
            "[bold blue]🍳 Enhanced Recipe Analyzer[/bold blue]\n"
            "[dim]AI-powered Instagram recipe extraction with batch processing[/dim]",
            expand=False,
        ),
    )

    try:
        # Load environment
        environment = env.Env.get_env()

        # Initialize components
        console.print("🔧 Initializing components...")

        extractor = InstagramExtractor(
            username=environment.INSTAGRAM_USERNAME,
            password=environment.INSTAGRAM_PASSWORD,
        )

        analyzer = EnhancedRecipeAnalyzer(
            openai_api_key=environment.OPENAI_API_KEY,
            enable_caching=args.cache,
        )

        # Extract posts
        posts = extractor.extract_saved_posts(
            collection_id=args.collection_id,
            limit=args.limit,
        )

        if not posts:
            console.print("❌ No posts found in collection")
            return

        # Show cost estimates
        show_cost_estimate(analyzer, posts, args.mode)

        # Confirm processing
        if not args.no_confirm and not confirm_processing(args.mode, len(posts)):
            console.print("❌ Processing cancelled")
            return

        # Setup progress tracking
        progress_tracker = ProgressTracker()

        def progress_callback(description: str, completed: int, total: int):
            progress_tracker.update(description, completed, total)

        # Start analysis
        console.print(f"\n🚀 Starting analysis in [bold]{args.mode}[/bold] mode...")

        progress_tracker.start("Analyzing recipes...", len(posts))

        start_time = time.time()

        recipes = analyzer.analyze_posts_batch_mode(
            posts=posts,
            processing_mode=args.mode,
            progress_callback=progress_callback,
        )

        progress_tracker.stop()

        elapsed_time = time.time() - start_time

        # Show results
        console.print(f"\n✅ Analysis completed in {elapsed_time:.1f} seconds")

        display_analysis_summary(recipes)

        # Save results
        save_results(recipes, args.output)

        console.print(
            f"\n🎉 [bold green]All done![/bold green] Check {args.output} for your analyzed recipes.",
        )

    except KeyboardInterrupt:
        console.print("\n❌ Process interrupted by user")
        sys.exit(1)

    except Exception as e:
        console.print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
