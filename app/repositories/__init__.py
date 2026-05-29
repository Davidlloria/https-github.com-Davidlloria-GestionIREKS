from app.repositories.contact_repository import ContactRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.distributor_repository import DistributorRepository
from app.repositories.provider_repository import ProviderRepository
from app.repositories.ingredient_repository import IngredientIreksRepository, IngredientStdRepository
from app.repositories.recipe_repository import RecipeRepository

__all__ = [
    "ContactRepository",
    "CustomerRepository",
    "DistributorRepository",
    "ProviderRepository",
    "IngredientIreksRepository",
    "IngredientStdRepository",
    "RecipeRepository",
]
