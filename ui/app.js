// ====================================
// Recipe Browser Application
// ====================================

// Global state
let recipes = [];
let filteredRecipes = [];
let activeFilters = new Set();

// DOM Elements
const elements = {
    searchInput: () => document.getElementById("search-input"),
    recipeGrid: () => document.getElementById("recipe-grid"),
    loading: () => document.getElementById("loading"),
    noResults: () => document.getElementById("no-results"),
    fileUploadSection: () => document.getElementById("file-upload-section"),
    jsonFileInput: () => document.getElementById("json-file-input"),
    clearFiltersBtn: () => document.getElementById("clear-filters"),
    activeFilters: () => document.getElementById("active-filters"),
    activeFilterTags: () => document.getElementById("active-filter-tags"),

    // Filter containers
    cuisineFilters: () => document.getElementById("cuisine-filters"),
    cookingFilters: () => document.getElementById("cooking-filters"),
    occasionFilters: () => document.getElementById("occasion-filters"),

    // Stats
    totalRecipes: () => document.getElementById("total-recipes"),
    showingRecipes: () => document.getElementById("showing-recipes"),
    uniqueIngredients: () => document.getElementById("unique-ingredients"),
    avgConfidence: () => document.getElementById("avg-confidence"),
};

// ====================================
// Application Initialization
// ====================================

async function init() {
    try {
        await loadRecipes();
        setupEventListeners();
        renderFilters();
        renderRecipes();
        updateStats();
        console.log("🍳 Recipe browser initialized successfully!");
    } catch (error) {
        console.error("⚠️ Error initializing app:", error);
        showError();
    }
}

// ====================================
// Data Loading
// ====================================

async function loadRecipes() {
    try {
        const response = await fetch("../analyzed_recipes.json");
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        recipes = await response.json();
        recipes = recipes.recipes;
        filteredRecipes = [...recipes];
        console.log(`✅ Loaded ${recipes.length} recipes successfully!`);
        hideFileUpload();
    } catch (error) {
        console.error("⚠️ Error loading recipes:", error);
        console.log("You can either:");
        console.log("1. Use the file picker above to load your JSON");
        console.log("2. Or serve this via HTTP (python -m http.server 8000)");

        showFileUpload();
        loadSampleData();
    }
}

function loadSampleData() {
    recipes = [
        {
            post_id: 3636866290532790354,
            title: "� Sample Recipe - Upload your JSON!",
            proteins: ["tofu"],
            vegetables: ["mushrooms", "carrots", "napa cabbage"],
            key_ingredients: ["rice_paper", "soy_sauce", "sesame_oil"],
            cooking_method: ["pan_frying"],
            equipment: ["pan"],
            dietary_tags: ["vegan", "gluten_free", "dairy_free"],
            texture_tags: ["crispy", "chewy"],
            flavor_tags: ["savory"],
            season_tags: ["other"],
            occasion_tags: ["quick", "make_ahead", "party", "snack"],
            cuisine_type: "asian",
            difficulty: "medium",
            confidence_score: 0.9,
            cooking_time: "null",
            total_time: "null",
        },
    ];
    filteredRecipes = [...recipes];
}

// ====================================
// File Upload Handling
// ====================================

function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function (e) {
        try {
            recipes = JSON.parse(e.target.result);
            filteredRecipes = [...recipes];
            console.log(`✅ Loaded ${recipes.length} recipes from file!`);

            renderFilters();
            renderRecipes();
            updateStats();
            hideFileUpload();
            showSuccessMessage(
                `Successfully loaded ${recipes.length} recipes!`
            );
        } catch (error) {
            showError("Error parsing JSON file. Please check the format.");
            console.error("⚠️ JSON parse error:", error);
        }
    };
    reader.readAsText(file);
}

function showFileUpload() {
    const section = elements.fileUploadSection();
    if (section) section.style.display = "block";
}

function hideFileUpload() {
    const section = elements.fileUploadSection();
    if (section) section.style.display = "none";
}

// ====================================
// Filter Management
// ====================================

function renderFilters() {
    const cuisineContainer = elements.cuisineFilters();
    const cookingContainer = elements.cookingFilters();
    const occasionContainer = elements.occasionFilters();

    // Extract unique values for filters
    const filterData = extractFilterData();

    // Clear existing filters
    cuisineContainer.innerHTML = "";
    cookingContainer.innerHTML = "";
    occasionContainer.innerHTML = "";

    // Render cuisine and dietary filters
    filterData.cuisines.forEach((cuisine) => {
        cuisineContainer.appendChild(
            createFilterButton(cuisine, "cuisine", "🌍")
        );
    });
    filterData.dietary.forEach((diet) => {
        cuisineContainer.appendChild(createFilterButton(diet, "dietary", "🥬"));
    });

    // Render cooking filters
    filterData.methods.forEach((method) => {
        cookingContainer.appendChild(
            createFilterButton(method, "method", "🔥")
        );
    });
    filterData.equipment.forEach((eq) => {
        cookingContainer.appendChild(createFilterButton(eq, "equipment", "🔧"));
    });
    filterData.difficulties.forEach((diff) => {
        cookingContainer.appendChild(
            createFilterButton(diff, "difficulty", "⭐")
        );
    });

    // Render occasion filters
    filterData.occasions.forEach((occasion) => {
        occasionContainer.appendChild(
            createFilterButton(occasion, "occasion", "🕒")
        );
    });
}

function extractFilterData() {
    const cuisines = new Set();
    const dietary = new Set();
    const methods = new Set();
    const equipment = new Set();
    const occasions = new Set();
    const difficulties = new Set();

    recipes.forEach((recipe) => {
        if (recipe.cuisine_type) cuisines.add(recipe.cuisine_type);
        if (recipe.dietary_tags)
            recipe.dietary_tags.forEach((tag) => dietary.add(tag));
        if (recipe.cooking_method)
            recipe.cooking_method.forEach((method) => methods.add(method));
        if (recipe.equipment)
            recipe.equipment.forEach((eq) => equipment.add(eq));
        if (recipe.occasion_tags)
            recipe.occasion_tags.forEach((occ) => occasions.add(occ));
        if (recipe.difficulty) difficulties.add(recipe.difficulty);
    });

    return {
        cuisines: [...cuisines].sort(),
        dietary: [...dietary].sort(),
        methods: [...methods].sort(),
        equipment: [...equipment].sort(),
        occasions: [...occasions].sort(),
        difficulties: [...difficulties].sort(),
    };
}

function createFilterButton(value, type, emoji) {
    const button = document.createElement("button");
    button.className =
        "filter-btn px-3 py-1 text-sm rounded-full transition-all";
    button.innerHTML = `${emoji} ${value.replace(/_/g, " ")}`;
    button.onclick = () => toggleFilter(value, type, button);
    return button;
}

function toggleFilter(value, type, button) {
    const filterKey = `${type}:${value}`;

    if (activeFilters.has(filterKey)) {
        activeFilters.delete(filterKey);
        button.classList.remove("filter-active");
    } else {
        activeFilters.add(filterKey);
        button.classList.add("filter-active");
    }

    applyFilters();
    updateActiveFiltersDisplay();
}

function clearFilters() {
    activeFilters.clear();
    document.querySelectorAll(".filter-active").forEach((btn) => {
        btn.classList.remove("filter-active");
    });
    elements.searchInput().value = "";
    applyFilters();
    updateActiveFiltersDisplay();
}

// ====================================
// Filtering and Search
// ====================================

function applyFilters() {
    const searchTerm = elements.searchInput().value.toLowerCase();

    filteredRecipes = recipes.filter((recipe) => {
        // Text search
        if (searchTerm && !matchesSearchTerm(recipe, searchTerm)) {
            return false;
        }

        // Filter matching
        return matchesActiveFilters(recipe);
    });

    renderRecipes();
    updateStats();
}

function matchesSearchTerm(recipe, searchTerm) {
    const searchable = [
        recipe.title,
        ...(recipe.ingredients || []),
        ...(recipe.proteins || []),
        ...(recipe.vegetables || []),
        ...(recipe.key_ingredients || []),
    ]
        .join(" ")
        .toLowerCase();

    return searchable.includes(searchTerm);
}

function matchesActiveFilters(recipe) {
    for (const filterKey of activeFilters) {
        const [type, value] = filterKey.split(":");

        switch (type) {
            case "cuisine":
                if (recipe.cuisine_type !== value) return false;
                break;
            case "dietary":
                if (!recipe.dietary_tags?.includes(value)) return false;
                break;
            case "method":
                if (!recipe.cooking_method?.includes(value)) return false;
                break;
            case "equipment":
                if (!recipe.equipment?.includes(value)) return false;
                break;
            case "occasion":
                if (!recipe.occasion_tags?.includes(value)) return false;
                break;
            case "difficulty":
                if (recipe.difficulty !== value) return false;
                break;
        }
    }

    return true;
}

function updateActiveFiltersDisplay() {
    const container = elements.activeFilters();
    const tagsContainer = elements.activeFilterTags();

    if (activeFilters.size === 0) {
        container.classList.add("hidden");
        return;
    }

    container.classList.remove("hidden");
    tagsContainer.innerHTML = Array.from(activeFilters)
        .map((filterKey) => {
            const [type, value] = filterKey.split(":");
            return `<span class="tag tag-difficulty" onclick="removeFilter('${filterKey}')" style="cursor: pointer;">${value.replace(
                /_/g,
                " "
            )} ✕</span>`;
        })
        .join("");
}

function removeFilter(filterKey) {
    activeFilters.delete(filterKey);
    applyFilters();
    updateActiveFiltersDisplay();

    // Update button state
    const [type, value] = filterKey.split(":");
    const button = Array.from(document.querySelectorAll(".filter-btn")).find(
        (btn) => btn.textContent.includes(value.replace(/_/g, " "))
    );
    if (button) button.classList.remove("filter-active");
}

// ====================================
// Recipe Rendering
// ====================================

function renderRecipes() {
    const grid = elements.recipeGrid();
    const noResults = elements.noResults();
    const loading = elements.loading();

    // Hide loading
    loading.classList.add("hidden");

    if (filteredRecipes.length === 0) {
        grid.classList.add("hidden");
        noResults.classList.remove("hidden");
        return;
    }

    grid.classList.remove("hidden");
    noResults.classList.add("hidden");

    grid.innerHTML = filteredRecipes
        .map((recipe) => createRecipeCard(recipe))
        .join("");
}

function createRecipeCard(recipe) {
    const confidenceClass = getConfidenceClass(recipe.confidence_score);

    return `
        <div class="recipe-card bg-white rounded-lg shadow-sm hover:shadow-lg transition-all duration-300 overflow-hidden">
          <!-- Recipe Image -->
            ${
                recipe.thumbnail_url
                    ? `
            <div class="relative h-48 overflow-hidden">
                <img src="${recipe.thumbnail_url}"
                     alt="${recipe.title}"
                     class="w-full h-full object-cover transition-transform duration-300 hover:scale-105"
                     onerror="this.parentElement.innerHTML='<div class=\\'recipe-image-placeholder h-48 text-white text-2xl\\'>🍽️</div>'">
                <div class="absolute top-2 right-2">
                    <span class="${confidenceClass} text-xs font-medium px-2 py-1 rounded-full bg-white/90 backdrop-blur-sm">${Math.round(
                          recipe.confidence_score * 100
                      )}%</span>
                </div>
            </div>
            `
                    : `
            <div class="recipe-image-placeholder h-48 text-white text-2xl">🍽️</div>
            `
            }
            <div class="p-6">
                <!-- Header -->
                <div class="mb-4">
                    <h3 class="text-lg font-semibold text-gray-800 line-clamp-2">${
                        recipe.title
                    }</h3>
                    ${
                        !recipe.thumbnail_url
                            ? `<span class="${confidenceClass} text-sm font-medium">${Math.round(
                                  recipe.confidence_score * 100
                              )}%</span>`
                            : ""
                    }
                </div>

                <!-- Quick Info -->
                <div class="grid grid-cols-2 gap-2 mb-4 text-sm text-gray-600">
                    ${
                        recipe.cuisine_type
                            ? `<div>🌍 ${recipe.cuisine_type}</div>`
                            : ""
                    }
                    ${
                        recipe.difficulty
                            ? `<div>⭐ ${recipe.difficulty}</div>`
                            : ""
                    }
                    ${
                        recipe.total_time && recipe.total_time !== "null"
                            ? `<div>🕒 ${recipe.total_time}</div>`
                            : ""
                    }
                    ${
                        recipe.cooking_method?.length
                            ? `<div>🔥 ${recipe.cooking_method[0].replace(
                                  /_/g,
                                  " "
                              )}</div>`
                            : ""
                    }
                </div>

                <!-- Tags -->
                <div class="space-y-2">
                    ${renderTagSection(
                        recipe.proteins,
                        "tag-protein",
                        "proteins"
                    )}
                    ${renderTagSection(
                        recipe.vegetables?.slice(0, 5),
                        "tag-vegetable",
                        "vegetables",
                        recipe.vegetables?.length
                    )}
                    ${renderTagSection(
                        recipe.occasion_tags?.slice(0, 3),
                        "tag-occasion",
                        "occasions"
                    )}
                </div>

                <!-- Footer -->
                <div class="mt-4 pt-4 border-t border-gray-100 flex gap-2">
                    <button onclick="openRecipe('${recipe.post_id}')"
                            class="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors">
                        View Recipe
                    </button>
                    <button onclick="openInstagramPost('${recipe.post_id}')"
                            class="bg-gradient-to-r from-purple-500 to-pink-500 text-white py-2 px-3 rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all">
                        📸
                    </button>
                </div>
            </div>
        </div>
    `;
}

function renderTagSection(items, tagClass, label, totalCount) {
    if (!items || items.length === 0) return "";

    let html = "<div>";
    html += items
        .map((item) => `<span class="tag ${tagClass}">${item}</span>`)
        .join("");

    if (totalCount && totalCount > items.length) {
        html += `<span class="tag ${tagClass}">+${
            totalCount - items.length
        }</span>`;
    }

    html += "</div>";
    return html;
}

function getConfidenceClass(score) {
    if (score > 0.8) return "confidence-high";
    if (score > 0.6) return "confidence-medium";
    return "confidence-low";
}

// ====================================
// Statistics
// ====================================

function updateStats() {
    elements.totalRecipes().textContent = recipes.length;
    elements.showingRecipes().textContent = filteredRecipes.length;

    const allIngredients = new Set();
    recipes.forEach((recipe) => {
        if (recipe.vegetables)
            recipe.vegetables.forEach((v) => allIngredients.add(v));
        if (recipe.key_ingredients)
            recipe.key_ingredients.forEach((k) => allIngredients.add(k));
    });
    elements.uniqueIngredients().textContent = allIngredients.size;

    const avgConfidence =
        recipes.reduce((sum, r) => sum + (r.confidence_score || 0), 0) /
        recipes.length;
    elements.avgConfidence().textContent =
        Math.round(avgConfidence * 100) + "%";
}

// ====================================
// Event Handlers
// ====================================

function setupEventListeners() {
    elements.searchInput().addEventListener("input", applyFilters);
    elements.clearFiltersBtn().addEventListener("click", clearFilters);
    elements.jsonFileInput().addEventListener("change", handleFileUpload);
}

// ====================================
// Navigation Functions - UPDATED
// ====================================

function openRecipe(postId) {
    // Navigate to recipe detail page
    window.location.href = `recipe.html?id=${postId}`;
}

function openInstagramPost(postId) {
    // Find the recipe and open Instagram post
    const recipe = recipes.find((r) => r.post_id == postId);
    if (recipe && recipe.code) {
        window.open(`https://instagram.com/p/${recipe.code}`, "_blank");
    } else {
        alert("Instagram post is not available for this recipe");
    }
}

// ====================================
// Utility Functions
// ====================================

function showSuccessMessage(message) {
    const successMsg = document.createElement("div");
    successMsg.className =
        "success-message bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4";
    successMsg.innerHTML = `✅ ${message}`;
    document
        .querySelector(".container")
        .insertBefore(successMsg, document.querySelector(".bg-white"));
    setTimeout(() => successMsg.remove(), 3000);
}

function showError(message = "Oops! Couldn't load recipes") {
    const loading = elements.loading();
    loading.innerHTML = `
        <div class="text-6xl mb-4">😵</div>
        <h3 class="text-xl font-semibold text-gray-700 mb-2">${message}</h3>
        <p class="text-gray-600">Make sure your analyzed_recipes.json file is accessible</p>
    `;
}

// ====================================
// Initialize App
// ====================================

// Start the application when DOM is loaded
document.addEventListener("DOMContentLoaded", init);
