// ====================================
// Recipe Detail Page Application
// ====================================

// Global state
let currentRecipe = null;
let allRecipes = [];

// DOM Elements
const elements = {
    recipeContent: () => document.getElementById("recipe-content"),
    recipeLoading: () => document.getElementById("recipe-loading"),
    recipeError: () => document.getElementById("recipe-error"),

    // Recipe details
    recipeTitle: () => document.getElementById("recipe-title"),
    recipeConfidence: () => document.getElementById("recipe-confidence"),
    recipeImageContainer: () =>
        document.getElementById("recipe-image-container"),

    // Quick info
    cuisineValue: () => document.getElementById("cuisine-value"),
    difficultyValue: () => document.getElementById("difficulty-value"),
    servingsValue: () => document.getElementById("servings-value"),
    prepTimeValue: () => document.getElementById("prep-time-value"),
    cookTimeValue: () => document.getElementById("cook-time-value"),
    totalTimeValue: () => document.getElementById("total-time-value"),

    // Content sections
    ingredientsList: () => document.getElementById("ingredients-list"),
    instructionsList: () => document.getElementById("instructions-list"),
    originalCaption: () => document.getElementById("original-caption"),

    // Tag sections
    proteinsSection: () => document.getElementById("proteins-section"),
    vegetablesSection: () => document.getElementById("vegetables-section"),
    keyIngredientsSection: () =>
        document.getElementById("key-ingredients-section"),
    cookingMethodSection: () =>
        document.getElementById("cooking-method-section"),
    equipmentSection: () => document.getElementById("equipment-section"),
    dietarySection: () => document.getElementById("dietary-section"),
    occasionSection: () => document.getElementById("occasion-section"),

    // Tag containers
    proteinsTags: () => document.getElementById("proteins-tags"),
    vegetablesTags: () => document.getElementById("vegetables-tags"),
    keyIngredientsTags: () => document.getElementById("key-ingredients-tags"),
    cookingMethodTags: () => document.getElementById("cooking-method-tags"),
    equipmentTags: () => document.getElementById("equipment-tags"),
    dietaryTags: () => document.getElementById("dietary-tags"),
    occasionTags: () => document.getElementById("occasion-tags"),

    // Buttons
    viewOriginalBtn: () => document.getElementById("view-original-btn"),
};

// ====================================
// Application Initialization
// ====================================

async function init() {
    try {
        // Get recipe ID from URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const recipeId = urlParams.get("id");

        if (!recipeId) {
            showError("No recipe ID provided");
            return;
        }

        await loadRecipes();
        await loadRecipe(recipeId);

        console.log("🍳 Recipe detail page initialized successfully!");
    } catch (error) {
        console.error("⚠️ Error initializing recipe page:", error);
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
        allRecipes = await response.json();
        console.log(`✅ Loaded ${allRecipes.length} recipes for lookup`);
    } catch (error) {
        console.error("⚠️ Error loading recipes:", error);
        throw error;
    }
}

async function loadRecipe(recipeId) {
    try {
        // Find the recipe by ID
        currentRecipe = allRecipes.find(
            (r) => String(r.post_id) === String(recipeId)
        );

        if (!currentRecipe) {
            throw new Error(`Recipe with ID ${recipeId} not found`);
        }

        renderRecipe(currentRecipe);
    } catch (error) {
        console.error("⚠️ Error loading recipe:", error);
        showError();
    }
}

// ====================================
// Recipe Rendering
// ====================================

function renderRecipe(recipe) {
    // Hide loading, show content
    elements.recipeLoading().classList.add("hidden");
    elements.recipeError().classList.add("hidden");
    elements.recipeContent().classList.remove("hidden");

    // Set title and confidence
    elements.recipeTitle().textContent = recipe.title;

    const confidence = Math.round(recipe.confidence_score * 100);
    const confidenceEl = elements.recipeConfidence();
    confidenceEl.textContent = `${confidence}% confidence`;
    confidenceEl.className = `${getConfidenceClass(
        recipe.confidence_score
    )} font-medium`;

    // Render image
    renderRecipeImage(recipe);

    // Render quick info
    renderQuickInfo(recipe);

    // Render tag sections
    renderTagSections(recipe);

    // Render ingredients
    renderIngredients(recipe);

    // Render instructions
    renderInstructions(recipe);

    // Render original caption
    elements.originalCaption().textContent = recipe.caption;
}

function renderRecipeImage(recipe) {
    const container = elements.recipeImageContainer();

    if (recipe.thumbnail_url) {
        container.innerHTML = `
            <img src="${recipe.thumbnail_url}"
                 alt="${recipe.title}"
                 class="w-full h-full object-cover"
                 onerror="this.parentElement.innerHTML='<div class=\\'recipe-image-placeholder h-full text-white\\'>🍽️</div>'">
        `;
    } else {
        container.innerHTML = `
            <div class="recipe-image-placeholder h-full text-white text-4xl">🍽️</div>
        `;
    }
}

function renderQuickInfo(recipe) {
    elements.cuisineValue().textContent = recipe.cuisine_type
        ? formatValue(recipe.cuisine_type)
        : "-";
    elements.difficultyValue().textContent = recipe.difficulty
        ? formatValue(recipe.difficulty)
        : "-";
    elements.servingsValue().textContent = recipe.servings || "-";
    elements.prepTimeValue().textContent = recipe.prep_time || "-";
    elements.cookTimeValue().textContent = recipe.cooking_time || "-";
    elements.totalTimeValue().textContent = recipe.total_time || "-";
}

function renderTagSections(recipe) {
    renderTagSection("proteins", recipe.proteins, "tag-protein");
    renderTagSection("vegetables", recipe.vegetables, "tag-vegetable");
    renderTagSection("keyIngredients", recipe.key_ingredients, "tag-method");
    renderTagSection("cookingMethod", recipe.cooking_method, "tag-method");
    renderTagSection("equipment", recipe.equipment, "tag-equipment");
    renderTagSection("dietary", recipe.dietary_tags, "tag-vegetable");
    renderTagSection("occasion", recipe.occasion_tags, "tag-occasion");
}

function renderTagSection(sectionName, tags, tagClass) {
    const section = elements[`${sectionName}Section`]();
    const container = elements[`${sectionName}Tags`]();

    if (!tags || tags.length === 0) {
        section.classList.add("hidden");
        return;
    }

    section.classList.remove("hidden");
    container.innerHTML = tags
        .map(
            (tag) => `<span class="tag ${tagClass}">${formatValue(tag)}</span>`
        )
        .join("");
}

function renderIngredients(recipe) {
    const container = elements.ingredientsList();

    if (!recipe.ingredients || recipe.ingredients.length === 0) {
        container.innerHTML =
            '<p class="text-gray-600 italic">No ingredients listed</p>';
        return;
    }

    container.innerHTML = recipe.ingredients
        .map(
            (ingredient) => `
            <div class="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                <span class="text-green-600 mt-1">✓</span>
                <span class="text-gray-800">${ingredient}</span>
            </div>
        `
        )
        .join("");
}

function renderInstructions(recipe) {
    const container = elements.instructionsList();

    if (!recipe.instructions || recipe.instructions.length === 0) {
        container.innerHTML =
            '<p class="text-gray-600 italic">No instructions provided</p>';
        return;
    }

    container.innerHTML = recipe.instructions
        .map(
            (instruction, index) => `
            <div class="flex items-start gap-4 p-4 bg-blue-50 rounded-lg">
                <span class="bg-blue-600 text-white rounded-full w-8 h-8 flex items-center justify-center text-sm font-bold flex-shrink-0 mt-1">
                    ${index + 1}
                </span>
                <span class="text-gray-800 leading-relaxed">${instruction}</span>
            </div>
        `
        )
        .join("");
}

// ====================================
// Navigation & Actions
// ====================================

function goBack() {
    window.history.back();
}

function viewOriginal() {
    if (currentRecipe && currentRecipe.code) {
        window.open(`https://instagram.com/p/${currentRecipe.code}`, "_blank");
    } else {
        alert("Original Instagram post is not available");
    }
}

// ====================================
// Utility Functions
// ====================================

function formatValue(value) {
    if (!value) return "-";
    return value.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

function getConfidenceClass(score) {
    if (score > 0.8) return "text-green-600";
    if (score > 0.6) return "text-orange-600";
    return "text-red-600";
}

function showError(message = "Recipe not found") {
    elements.recipeLoading().classList.add("hidden");
    elements.recipeContent().classList.add("hidden");
    elements.recipeError().classList.remove("hidden");

    const errorEl = elements.recipeError();
    errorEl.querySelector("h3").textContent = message;
}

// ====================================
// Initialize App
// ====================================

// Start the application when DOM is loaded
document.addEventListener("DOMContentLoaded", init);
