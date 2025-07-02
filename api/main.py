"""Main FastAPI application.

Configures the API with all routers, middleware, and exception handlers.
"""

from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.v1.auth import router as auth_router
from api.v1.health import router as health_router
from api.v1.game import router as game_router
from core.config import get_settings
from core.database import init_db, close_db
from core.engine.plugin_manager import PluginManager

# Import feature routers
from features.ceo_system.api.ceo_endpoints import router as ceo_router
from features.expansion.api.expansion_endpoints import router as expansion_router
from features.products.api.product_endpoints import router as products_router
from features.investments.api.investment_endpoints import router as investments_router
from features.regulatory.api.compliance_endpoints import router as regulatory_router
from features.market_events.api.market_events_endpoints import router as market_events_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.
    
    Handles startup and shutdown tasks.
    """
    # Startup
    await init_db()
    
    # Initialize plugin manager (simplified for MVP)
    plugin_manager = PluginManager()
    # Skip plugin initialization for MVP to avoid abstract class issues
    # await plugin_manager.initialize(session, None)
    app.state.plugin_manager = plugin_manager
    
    yield
    
    # Shutdown
    # Skip plugin shutdown for MVP since we didn't initialize plugins
    # if hasattr(plugin_manager, 'shutdown'):
    #     await plugin_manager.shutdown()
    await close_db()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Insurance Manager - Educational Simulation Game",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle validation errors."""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors."""
    # Log the error here
    if settings.debug:
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__}
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Root endpoint
@app.get("/", response_model=Dict[str, Any])
async def root() -> Dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Insurance Manager API",
        "documentation": "/api/docs",
        "health": "/api/v1/health"
    }


# Register routers
# Core API routes
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(game_router)

# Feature routes
app.include_router(ceo_router, prefix="/api/v1")
app.include_router(expansion_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(investments_router, prefix="/api/v1")
app.include_router(regulatory_router, prefix="/api/v1")
app.include_router(market_events_router, prefix="/api/v1")


# Middleware for request ID tracking
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests for tracking."""
    import uuid
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response


# Startup message
@app.on_event("startup")
async def startup_message():
    """Print startup message."""
    print(f"🚀 {settings.app_name} v{settings.app_version} started!")
    print(f"📚 API documentation available at http://localhost:8000/api/docs")
    print(f"🔧 Debug mode: {settings.debug}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    ) 