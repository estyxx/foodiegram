/**
 * Enhanced Recipe Browser Application
 * A clean, modular approach to recipe browsing and filtering
 */

class RecipeBrowser {
    constructor() {
        this.recipes = [];
        this.filteredRecipes = [];
        this.activeFilters = new Set();
        this.elements = this.initializeElements();
        this.stats = new RecipeStats();
        this.filters = new FilterManager(this);
        this.renderer = new RecipeRenderer(this);
    }

    /**
     * Initialize DOM element references
     */
    initializeElements() {
        return {
            // Main containers
            recipeGrid: () => document.getElementById("recipe-grid"),
            loading: () => document.getElementById("loading"),
            noResults: () => document.getElementById("no-results"),
            searchInput: () => document.getElementById("search-input"),
            clearFiltersBtn: () => document.getElementById("clear-filters"),

            // Filter containers
            cuisineFilters: () => document.getElementById("cuisine-filters"),
            cookingFilters: () => document.getElementById("cooking-filters"),
            occasionFilters: () => document.getElementById("occasion-filters"),

            // Active filters
            activeFilters: () => document.getElementById("active-filters"),
            activeFilterTags: () =>
                document.getElementById("active-filter-tags"),

            // Stats
            totalRecipes: () => document.getElementById("total-recipes"),
            showingRecipes: () => document.getElementById("showing-recipes"),
            uniqueIngredients: () =>
                document.getElementById("unique-ingredients"),
            avgCookTime: () => document.getElementById("avg-cook-time"),
        };
    }

    /**
     * Application initialization
     */
    async init() {
        try {
            await this.loadRecipes();
            this.setupEventListeners();
            this.filters.render();
            this.renderer.renderRecipes();
            this.stats.update();

            console.log("🍳 Recipe browser initialized successfully!");
        } catch (error) {
            console.error("⚠️ Error initializing app:", error);
            this.showError();
        }
    }

    /**
     * Load recipes from JSON file
     */
    async loadRecipes() {
        try {
            const response = await fetch(
                "../data/extracted_recipes_realtime.json"
            );
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            this.recipes = await response.json();
            this.filteredRecipes = [...this.recipes];

            console.log(
                `✅ Loaded ${this.recipes.length} recipes successfully!`
            );
        } catch (error) {
            console.error("⚠️ Error loading recipes:", error);
            this.recipes = [];
            this.filteredRecipes = [];
            throw error;
        }
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        this.elements
            .searchInput()
            .addEventListener("input", () => this.applyFilters());
        this.elements
            .clearFiltersBtn()
            .addEventListener("click", () => this.clearFilters());

        // Add keyboard shortcuts
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                this.clearFilters();
            }
        });
    }

    /**
     * Apply all active filters
     */
    applyFilters() {
        const searchTerm = this.elements.searchInput().value.toLowerCase();

        this.filteredRecipes = this.recipes.filter((recipe) => {
            // Text search filter
            if (searchTerm && !this.matchesSearchTerm(recipe, searchTerm)) {
                return false;
            }

            // Active filters
            return this.matchesActiveFilters(recipe);
        });

        this.renderer.renderRecipes();
        this.stats.update();
    }

    /**
     * Check if recipe matches search term
     */
    matchesSearchTerm(recipe, searchTerm) {
        const searchableFields = [
            recipe.title,
            ...(recipe.ingredients || []),
            ...(recipe.proteins || []),
            ...(recipe.vegetables || []),
        ];

        const searchableText = searchableFields.join(" ").toLowerCase();
        return searchableText.includes(searchTerm);
    }

    /**
     * Check if recipe matches all active filters
     */
    matchesActiveFilters(recipe) {
        for (const filterKey of this.activeFilters) {
            const [type, value] = filterKey.split(":");

            const filterMatchers = {
                cuisine: () => recipe.cuisine_type === value,
                dietary: () => recipe.dietary_tags?.includes(value),
                method: () => recipe.cooking_methods?.includes(value),
                equipment: () => recipe.equipment?.includes(value),
                occasion: () => recipe.occasion?.includes(value),
                difficulty: () => recipe.difficulty === value,
            };

            const matcher = filterMatchers[type];
            if (matcher && !matcher()) {
                return false;
            }
        }

        return true;
    }

    /**
     * Clear all filters
     */
    clearFilters() {
        this.activeFilters.clear();
        document.querySelectorAll(".filter-active").forEach((btn) => {
            btn.classList.remove("filter-active");
        });
        this.elements.searchInput().value = "";
        this.applyFilters();
        this.filters.updateActiveFiltersDisplay();
    }

    /**
     * Navigation methods
     */
    openRecipe(postId) {
        window.location.href = `recipe.html?id=${postId}`;
    }

    openInstagramPost(postId) {
        const recipe = this.recipes.find((r) => r.post_id == postId);
        if (recipe?.code) {
            window.open(`https://instagram.com/p/${recipe.code}`, "_blank");
        } else {
            alert("Instagram post is not available for this recipe");
        }
    }

    /**
     * Show error state
     */
    showError(message = "Oops! Couldn't load recipes") {
        const loading = this.elements.loading();
        loading.innerHTML = `
            <div class="text-6xl mb-4">😵</div>
            <h3 class="text-xl font-semibold text-gray-700 mb-2">${message}</h3>
            <p class="text-gray-600">Make sure your extracted_recipes_realtime.json file is accessible</p>
        `;
    }
}

/**
 * Filter management system
 */
class FilterManager {
    constructor(app) {
        this.app = app;
    }

    /**
     * Render all filter groups
     */
    render() {
        const filterData = this.extractFilterData();

        this.renderFilterGroup("cuisine-filters", [
            ...filterData.cuisines.map((cuisine) => ({
                value: cuisine,
                type: "cuisine",
                emoji: "🌍",
            })),
            ...filterData.dietary.map((diet) => ({
                value: diet,
                type: "dietary",
                emoji: "🥬",
            })),
        ]);

        this.renderFilterGroup("cooking-filters", [
            ...filterData.methods.map((method) => ({
                value: method,
                type: "method",
                emoji: "🔥",
            })),
            ...filterData.equipment.map((eq) => ({
                value: eq,
                type: "equipment",
                emoji: "🔧",
            })),
            ...filterData.difficulties.map((diff) => ({
                value: diff,
                type: "difficulty",
                emoji: "⭐",
            })),
        ]);

        this.renderFilterGroup("occasion-filters", [
            ...filterData.occasions.map((occasion) => ({
                value: occasion,
                type: "occasion",
                emoji: "🕒",
            })),
        ]);
    }

    /**
     * Render individual filter group
     */
    renderFilterGroup(containerId, filters) {
        const container = this.app.elements[this.toCamelCase(containerId)]();
        container.innerHTML = "";

        filters.forEach((filter) => {
            const button = this.createFilterButton(
                filter.value,
                filter.type,
                filter.emoji
            );
            container.appendChild(button);
        });
    }

    /**
     * Extract unique filter values from recipes
     */
    extractFilterData() {
        const data = {
            cuisines: new Set(),
            dietary: new Set(),
            methods: new Set(),
            equipment: new Set(),
            occasions: new Set(),
            difficulties: new Set(),
        };

        this.app.recipes.forEach((recipe) => {
            if (recipe.cuisine_type) data.cuisines.add(recipe.cuisine_type);
            recipe.dietary_tags?.forEach((tag) => data.dietary.add(tag));
            recipe.cooking_methods?.forEach((method) =>
                data.methods.add(method)
            );
            recipe.equipment?.forEach((eq) => data.equipment.add(eq));
            recipe.occasion?.forEach((occ) => data.occasions.add(occ));
            if (recipe.difficulty) data.difficulties.add(recipe.difficulty);
        });

        // Convert sets to sorted arrays
        return Object.fromEntries(
            Object.entries(data).map(([key, set]) => [key, [...set].sort()])
        );
    }

    /**
     * Create filter button element
     */
    createFilterButton(value, type, emoji) {
        const button = document.createElement("button");
        button.className =
            "filter-btn px-3 py-1 text-sm rounded-full transition-all";
        button.innerHTML = `${emoji} ${value.replace(/_/g, " ")}`;
        button.onclick = () => this.toggleFilter(value, type, button);
        return button;
    }

    /**
     * Toggle filter state
     */
    toggleFilter(value, type, button) {
        const filterKey = `${type}:${value}`;

        if (this.app.activeFilters.has(filterKey)) {
            this.app.activeFilters.delete(filterKey);
            button.classList.remove("filter-active");
        } else {
            this.app.activeFilters.add(filterKey);
            button.classList.add("filter-active");
        }

        this.app.applyFilters();
        this.updateActiveFiltersDisplay();
    }

    /**
     * Update active filters display
     */
    updateActiveFiltersDisplay() {
        const container = this.app.elements.activeFilters();
        const tagsContainer = this.app.elements.activeFilterTags();

        if (this.app.activeFilters.size === 0) {
            container.classList.add("hidden");
            return;
        }

        container.classList.remove("hidden");
        tagsContainer.innerHTML = Array.from(this.app.activeFilters)
            .map((filterKey) => {
                const [type, value] = filterKey.split(":");
                return `<span class="tag tag-difficulty cursor-pointer" onclick="app.filters.removeFilter('${filterKey}')">${value.replace(
                    /_/g,
                    " "
                )} ✕</span>`;
            })
            .join("");
    }

    /**
     * Remove specific filter
     */
    removeFilter(filterKey) {
        this.app.activeFilters.delete(filterKey);
        this.app.applyFilters();
        this.updateActiveFiltersDisplay();

        // Update button state
        const [type, value] = filterKey.split(":");
        const button = Array.from(
            document.querySelectorAll(".filter-btn")
        ).find((btn) => btn.textContent.includes(value.replace(/_/g, " ")));
        button?.classList.remove("filter-active");
    }

    /**
     * Convert kebab-case to camelCase
     */
    toCamelCase(str) {
        return str.replace(/-([a-z])/g, (g) => g[1].toUpperCase());
    }
}

/**
 * Recipe rendering system
 */
class RecipeRenderer {
    constructor(app) {
        this.app = app;
    }

    /**
     * Render recipe grid
     */
    renderRecipes() {
        const grid = this.app.elements.recipeGrid();
        const noResults = this.app.elements.noResults();
        const loading = this.app.elements.loading();

        // Hide loading state
        loading.classList.add("hidden");

        if (this.app.filteredRecipes.length === 0) {
            grid.classList.add("hidden");
            noResults.classList.remove("hidden");
            return;
        }

        grid.classList.remove("hidden");
        noResults.classList.add("hidden");

        // Render recipe cards
        grid.innerHTML = this.app.filteredRecipes
            .map((recipe) => this.createRecipeCard(recipe))
            .join("");
    }

    /**
     * Create individual recipe card
     */
    createRecipeCard(recipe) {
        return `
            <div class="recipe-card bg-white rounded-lg shadow-sm hover:shadow-lg overflow-hidden">
                ${this.renderRecipeImage(recipe)}

                <div class="card-content p-6">
                    <div class="mb-4">
                        <h3 class="text-lg font-semibold text-gray-800 line-clamp-2 mb-2">${
                            recipe.title
                        }</h3>
                    </div>

                    ${this.renderQuickInfo(recipe)}
                    ${this.renderTags(recipe)}

                    <div class="card-footer">
                        <div class="flex gap-2">
                            <button onclick="app.openRecipe('${
                                recipe.post_id
                            }')"
                                    class="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors">
                                View Recipe
                            </button>
                            <button onclick="app.openInstagramPost('${
                                recipe.post_id
                            }')"
                                    class="bg-gradient-to-r from-purple-500 to-pink-500 text-white py-2 px-3 rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all">
                                📸
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render recipe image
     */
    renderRecipeImage(recipe) {
        if (recipe.thumbnail_url) {
            return `
                <div class="relative h-48 overflow-hidden">
                    <img src="${recipe.thumbnail_url}"
                         alt="${recipe.title}"
                         class="w-full h-full object-cover transition-transform duration-300 hover:scale-105"
                         onerror="this.parentElement.innerHTML='<div class=\\'recipe-image-placeholder h-48 text-white text-2xl\\'>🍽️</div>'">
                </div>
            `;
        }
        return '<div class="recipe-image-placeholder h-48 text-white text-2xl">🍽️</div>';
    }

    /**
     * Render quick info grid
     */
    renderQuickInfo(recipe) {
        const infoItems = [
            {
                condition: recipe.cuisine_type,
                icon: "🌍",
                value: recipe.cuisine_type,
            },
            {
                condition: recipe.difficulty,
                icon: "⭐",
                value: recipe.difficulty,
            },
            {
                condition: recipe.total_time && recipe.total_time !== "unknown",
                icon: "🕒",
                value: recipe.total_time,
            },
            {
                condition: recipe.cooking_methods?.length,
                icon: "🔥",
                value: recipe.cooking_methods?.[0]?.replace(/_/g, " "),
            },
        ].filter((item) => item.condition);

        return `
            <div class="grid grid-cols-2 gap-2 mb-4 text-sm text-gray-600">
                ${infoItems
                    .map((item) => `<div>${item.icon} ${item.value}</div>`)
                    .join("")}
            </div>
        `;
    }

    /**
     * Render recipe tags
     */
    renderTags(recipe) {
        return `
            <div class="space-y-2 mb-4">
                ${this.renderTagSection(recipe.proteins, "tag-protein")}
                ${this.renderTagSection(
                    recipe.vegetables?.slice(0, 4),
                    "tag-vegetable",
                    recipe.vegetables?.length
                )}
                ${this.renderTagSection(
                    recipe.occasion?.slice(0, 3),
                    "tag-occasion"
                )}
            </div>
        `;
    }

    /**
     * Render individual tag section
     */
    renderTagSection(items, tagClass, totalCount) {
        if (!items?.length) return "";

        let html = items
            .map((item) => `<span class="tag ${tagClass}">${item}</span>`)
            .join("");

        if (totalCount && totalCount > items.length) {
            html += `<span class="tag ${tagClass}">+${
                totalCount - items.length
            }</span>`;
        }

        return html;
    }
}

/**
 * Statistics management
 */
class RecipeStats {
    constructor() {
        this.app = null; // Will be set when attached to app
    }

    /**
     * Update all statistics
     */
    update() {
        if (!this.app) {
            // Find app instance
            this.app = window.app;
        }

        this.updateBasicStats();
        this.updateAdvancedStats();
    }

    /**
     * Update basic statistics
     */
    updateBasicStats() {
        const elements = this.app.elements;

        elements.totalRecipes().textContent = this.app.recipes.length;
        elements.showingRecipes().textContent = this.app.filteredRecipes.length;

        // Count unique ingredients
        const allIngredients = new Set();
        this.app.recipes.forEach((recipe) => {
            recipe.vegetables?.forEach((v) => allIngredients.add(v));
            recipe.ingredients?.forEach((i) => allIngredients.add(i));
        });
        elements.uniqueIngredients().textContent = allIngredients.size;
    }

    /**
     * Update advanced statistics
     */
    updateAdvancedStats() {
        // Calculate average cook time
        const validTimes = this.app.recipes
            .map((r) => r.cook_time)
            .filter(
                (time) => time && time !== "unknown" && time.includes("minute")
            )
            .map((time) => parseInt(time.match(/\d+/)?.[0] || 0))
            .filter((time) => time > 0);

        const avgTime = validTimes.length
            ? Math.round(
                  validTimes.reduce((a, b) => a + b, 0) / validTimes.length
              )
            : 0;

        this.app.elements.avgCookTime().textContent = avgTime
            ? `${avgTime}min`
            : "-";
    }
}

/**
 * Application initialization
 */
let app;

document.addEventListener("DOMContentLoaded", () => {
    app = new RecipeBrowser();
    app.stats.app = app; // Attach stats to app
    app.init();
});

// Make app globally available for onclick handlers
window.app = app;
