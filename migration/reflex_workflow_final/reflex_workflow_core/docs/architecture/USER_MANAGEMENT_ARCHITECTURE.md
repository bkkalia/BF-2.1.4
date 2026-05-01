# User Management & Multi-Tenancy Architecture

**Purpose:** Complete guide for handling user accounts, profiles, personalization, and tenant data in BlackForest 3.0

---

## Database Architecture: Single vs Separate

### ✅ Recommended: Single Database, Logical Separation

**Why single database:**
- ✅ Simpler to manage (one backup, one connection pool)
- ✅ ACID transactions across user + tender data
- ✅ Easier queries (user favorites + tender details in one query)
- ✅ Lower operational complexity
- ✅ PostgreSQL can handle millions of rows easily

**Logical separation strategies:**
```sql
-- Option 1: Separate schemas
CREATE SCHEMA tender_data;  -- Portal, scraping, tenders
CREATE SCHEMA user_data;    -- Users, profiles, preferences
CREATE SCHEMA analytics;    -- Derived data, reports

-- Option 2: Table prefixes (simpler)
-- user_* tables for user data
-- tender_* tables for tender data
-- portal_* tables for portal config
```

### Database Layout

```
┌─────────────────────────────────────────────────────────────┐
│              PostgreSQL Primary Database                    │
│                                                             │
│  ┌────────────────────────────────────────────────────┐   │
│  │  USER DATA (Schema: user_data)                     │   │
│  │  - users                                            │   │
│  │  - user_profiles                                    │   │
│  │  - user_organizations                               │   │
│  │  - user_subscriptions                               │   │
│  │  - user_activity_log                                │   │
│  └────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌────────────────────────────────────────────────────┐   │
│  │  PERSONALIZATION (Schema: user_data)               │   │
│  │  - user_tender_favorites                            │   │
│  │  - user_alerts                                      │   │
│  │  - user_saved_searches                              │   │
│  │  - user_tender_notes                                │   │
│  │  - user_notifications                               │   │
│  └────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌────────────────────────────────────────────────────┐   │
│  │  TENDER DATA (Schema: tender_data)                 │   │
│  │  - portals                                          │   │
│  │  - portal_skills                                    │   │
│  │  - scraping_runs                                    │   │
│  │  - tenders                                          │   │
│  │  - department_snapshots                             │   │
│  └────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌────────────────────────────────────────────────────┐   │
│  │  ANALYTICS (Schema: analytics)                     │   │
│  │  - tender_trends                                    │   │
│  │  - portal_metrics                                   │   │
│  │  - user_engagement_metrics                          │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Redis Cache & Sessions                         │
│  - User sessions (JWT tokens)                               │
│  - Alert matching cache                                     │
│  - Rate limiting counters                                   │
│  - Real-time notifications queue                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Complete Database Schema: User Tables

### 1. User Authentication & Core Info

```sql
-- ============================================================================
-- USER AUTHENTICATION
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS user_data;
SET search_path TO user_data;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    
    -- Authentication
    email VARCHAR(255) UNIQUE NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    password_hash TEXT NOT NULL,  -- bcrypt hash
    
    -- Identity
    full_name VARCHAR(200) NOT NULL,
    phone VARCHAR(20),
    phone_verified BOOLEAN DEFAULT FALSE,
    
    -- Account status
    status VARCHAR(20) DEFAULT 'active',  -- 'active', 'suspended', 'deleted'
    account_type VARCHAR(20) DEFAULT 'free',  -- 'free', 'basic', 'premium', 'enterprise'
    
    -- Security
    failed_login_attempts INTEGER DEFAULT 0,
    last_failed_login TIMESTAMP,
    locked_until TIMESTAMP,
    two_factor_enabled BOOLEAN DEFAULT FALSE,
    two_factor_secret TEXT,
    
    -- Activity tracking
    last_login_at TIMESTAMP,
    last_login_ip INET,
    password_changed_at TIMESTAMP DEFAULT NOW(),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP  -- Soft delete
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status) WHERE status = 'active';
CREATE INDEX idx_users_account_type ON users(account_type);

-- ============================================================================
-- USER PROFILES & ORGANIZATIONS
-- ============================================================================

CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Professional info
    company_name VARCHAR(300),
    designation VARCHAR(100),
    industry_sector VARCHAR(100)[],  -- Array: ['construction', 'it', 'consultancy']
    
    -- Business details
    gst_number VARCHAR(20),
    pan_number VARCHAR(15),
    company_registration_number VARCHAR(50),
    annual_turnover_range VARCHAR(50),  -- '1-5cr', '5-10cr', etc.
    employee_count_range VARCHAR(50),   -- '10-50', '50-100', etc.
    years_in_business INTEGER,
    
    -- Geographic focus
    operating_states VARCHAR(100)[],  -- ['Bihar', 'Jharkhand', 'UP']
    head_office_city VARCHAR(100),
    head_office_state VARCHAR(100),
    
    -- Tender preferences
    preferred_tender_types VARCHAR(100)[],  -- ['construction', 'supply', 'consultancy']
    min_tender_value NUMERIC(15, 2),
    max_tender_value NUMERIC(15, 2),
    specializations TEXT[],  -- ['highway construction', 'bridge engineering']
    
    -- Contact preferences
    notification_preferences JSONB DEFAULT '{"email": true, "sms": false, "push": true}'::jsonb,
    timezone VARCHAR(50) DEFAULT 'Asia/Kolkata',
    language_preference VARCHAR(10) DEFAULT 'en',
    
    -- Profile completion
    profile_completion_percentage INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_profiles_sectors ON user_profiles USING gin(industry_sector);
CREATE INDEX idx_profiles_states ON user_profiles USING gin(operating_states);
CREATE INDEX idx_profiles_specializations ON user_profiles USING gin(specializations);

-- ============================================================================
-- ORGANIZATIONS (For enterprise users)
-- ============================================================================

CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    
    -- Organization info
    name VARCHAR(300) NOT NULL,
    org_type VARCHAR(50),  -- 'contractor', 'consultancy', 'supplier', 'government'
    
    -- Billing
    billing_email VARCHAR(255),
    billing_address TEXT,
    
    -- Subscription
    subscription_plan VARCHAR(50) DEFAULT 'free',  -- 'free', 'team', 'business', 'enterprise'
    subscription_status VARCHAR(20) DEFAULT 'active',
    subscription_starts_at TIMESTAMP,
    subscription_ends_at TIMESTAMP,
    
    -- Limits
    max_users INTEGER DEFAULT 1,
    max_alerts INTEGER DEFAULT 10,
    max_saved_searches INTEGER DEFAULT 5,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE organization_users (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    role VARCHAR(50) DEFAULT 'member',  -- 'owner', 'admin', 'member', 'viewer'
    joined_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(organization_id, user_id)
);

CREATE INDEX idx_org_users_org ON organization_users(organization_id);
CREATE INDEX idx_org_users_user ON organization_users(user_id);

-- ============================================================================
-- USER ACTIVITY LOGS (Audit trail)
-- ============================================================================

CREATE TABLE user_activity_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    action_type VARCHAR(50) NOT NULL,  -- 'login', 'search', 'favorite_add', 'alert_create', etc.
    action_details JSONB,
    
    ip_address INET,
    user_agent TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_activity_user ON user_activity_log(user_id, created_at DESC);
CREATE INDEX idx_activity_type ON user_activity_log(action_type);
CREATE INDEX idx_activity_date ON user_activity_log(created_at DESC);

-- Partition by month for performance
-- (implement partitioning as data grows)
```

### 2. Tender Personalization Features

```sql
-- ============================================================================
-- FAVORITES
-- ============================================================================

CREATE TABLE user_tender_favorites (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_data.users(id) ON DELETE CASCADE,
    tender_id INTEGER NOT NULL REFERENCES tender_data.tenders(id) ON DELETE CASCADE,
    
    -- Organization
    folder_name VARCHAR(100),  -- For organizing favorites
    tags VARCHAR(50)[],        -- User-defined tags
    
    -- Notes
    user_notes TEXT,
    priority VARCHAR(20),      -- 'high', 'medium', 'low'
    
    -- Status tracking
    bid_status VARCHAR(50),    -- 'planning', 'preparing', 'submitted', 'won', 'lost', 'withdrawn'
    bid_amount NUMERIC(15, 2),
    bid_submitted_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_id, tender_id)
);

CREATE INDEX idx_favorites_user ON user_tender_favorites(user_id, created_at DESC);
CREATE INDEX idx_favorites_tender ON user_tender_favorites(tender_id);
CREATE INDEX idx_favorites_folder ON user_tender_favorites(user_id, folder_name);
CREATE INDEX idx_favorites_status ON user_tender_favorites(user_id, bid_status);

-- ============================================================================
-- SMART ALERTS (Saved searches with notifications)
-- ============================================================================

CREATE TABLE user_alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_data.users(id) ON DELETE CASCADE,
    
    -- Alert configuration
    alert_name VARCHAR(200) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Search criteria (flexible JSON)
    criteria JSONB NOT NULL,
    /* Example criteria:
    {
        "keywords": ["road construction", "bridge"],
        "states": ["Bihar", "Jharkhand"],
        "min_value": 5000000,
        "max_value": 50000000,
        "departments": ["PWD", "NHAI"],
        "closing_date_range": "next_30_days",
        "exclude_keywords": ["supply only"]
    }
    */
    
    -- Notification settings
    notification_methods VARCHAR(20)[] DEFAULT ARRAY['email'],  -- ['email', 'sms', 'push']
    notification_frequency VARCHAR(20) DEFAULT 'immediate',  -- 'immediate', 'daily_digest', 'weekly_digest'
    notification_time TIME,  -- For digest notifications (e.g., '09:00:00')
    
    -- Tracking
    last_matched_at TIMESTAMP,
    last_notified_at TIMESTAMP,
    total_matches INTEGER DEFAULT 0,
    total_notifications_sent INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_alerts_user ON user_alerts(user_id);
CREATE INDEX idx_alerts_active ON user_alerts(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_alerts_criteria ON user_alerts USING gin(criteria);

-- ============================================================================
-- ALERT MATCHES (Track which tenders matched which alerts)
-- ============================================================================

CREATE TABLE user_alert_matches (
    id BIGSERIAL PRIMARY KEY,
    alert_id INTEGER NOT NULL REFERENCES user_alerts(id) ON DELETE CASCADE,
    tender_id INTEGER NOT NULL REFERENCES tender_data.tenders(id) ON DELETE CASCADE,
    
    matched_at TIMESTAMP DEFAULT NOW(),
    notified_at TIMESTAMP,
    notification_status VARCHAR(20),  -- 'pending', 'sent', 'failed', 'dismissed'
    
    -- User interaction
    viewed_at TIMESTAMP,
    clicked_at TIMESTAMP,
    
    UNIQUE(alert_id, tender_id)
);

CREATE INDEX idx_alert_matches_alert ON user_alert_matches(alert_id, matched_at DESC);
CREATE INDEX idx_alert_matches_notification ON user_alert_matches(notification_status) 
    WHERE notification_status = 'pending';

-- ============================================================================
-- SAVED SEARCHES (Quick access to common queries)
-- ============================================================================

CREATE TABLE user_saved_searches (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_data.users(id) ON DELETE CASCADE,
    
    search_name VARCHAR(200) NOT NULL,
    search_query JSONB NOT NULL,  -- Same structure as alert criteria
    
    -- Usage tracking
    last_used_at TIMESTAMP,
    use_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_saved_searches_user ON user_saved_searches(user_id, last_used_at DESC);

-- ============================================================================
-- TENDER NOTES & ANNOTATIONS
-- ============================================================================

CREATE TABLE user_tender_notes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_data.users(id) ON DELETE CASCADE,
    tender_id INTEGER NOT NULL REFERENCES tender_data.tenders(id) ON DELETE CASCADE,
    
    note_text TEXT NOT NULL,
    note_type VARCHAR(50),  -- 'general', 'technical', 'financial', 'risk'
    
    -- Collaboration (for organization users)
    is_shared BOOLEAN DEFAULT FALSE,  -- Share with org members
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tender_notes_user ON user_tender_notes(user_id);
CREATE INDEX idx_tender_notes_tender ON user_tender_notes(tender_id);

-- ============================================================================
-- NOTIFICATIONS (In-app notifications)
-- ============================================================================

CREATE TABLE user_notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_data.users(id) ON DELETE CASCADE,
    
    notification_type VARCHAR(50) NOT NULL,  -- 'alert_match', 'system', 'reminder', etc.
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    
    -- Links
    action_url TEXT,  -- Deep link to tender, alert, etc.
    related_tender_id INTEGER REFERENCES tender_data.tenders(id) ON DELETE SET NULL,
    related_alert_id INTEGER REFERENCES user_alerts(id) ON DELETE SET NULL,
    
    -- Status
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP,
    
    -- Delivery
    delivery_method VARCHAR(20),  -- 'in_app', 'email', 'sms'
    
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP  -- Auto-delete old notifications
);

CREATE INDEX idx_notifications_user ON user_notifications(user_id, created_at DESC);
CREATE INDEX idx_notifications_unread ON user_notifications(user_id, is_read) 
    WHERE is_read = FALSE;

-- ============================================================================
-- USER PREFERENCES (Granular settings)
-- ============================================================================

CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES user_data.users(id) ON DELETE CASCADE,
    
    -- Dashboard preferences
    default_view VARCHAR(50) DEFAULT 'grid',  -- 'grid', 'list', 'compact'
    tenders_per_page INTEGER DEFAULT 25,
    default_sort VARCHAR(50) DEFAULT 'closing_date',  -- 'closing_date', 'value', 'published_date'
    
    -- Alert preferences
    quiet_hours_start TIME,  -- e.g., '22:00:00'
    quiet_hours_end TIME,    -- e.g., '08:00:00'
    max_alerts_per_day INTEGER DEFAULT 50,
    
    -- Email preferences
    email_digest_frequency VARCHAR(20) DEFAULT 'daily',  -- 'immediate', 'daily', 'weekly', 'never'
    email_digest_time TIME DEFAULT '09:00:00',
    
    -- Display preferences
    show_expired_tenders BOOLEAN DEFAULT FALSE,
    highlight_urgent_tenders BOOLEAN DEFAULT TRUE,  -- Closing in <7 days
    
    -- Privacy
    profile_visibility VARCHAR(20) DEFAULT 'private',  -- 'public', 'organization', 'private'
    
    -- Advanced features
    enable_ai_recommendations BOOLEAN DEFAULT TRUE,
    enable_smart_suggestions BOOLEAN DEFAULT TRUE,
    
    preferences_json JSONB,  -- For future extensibility
    
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- API KEYS (For external integrations)
-- ============================================================================

CREATE TABLE user_api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_data.users(id) ON DELETE CASCADE,
    
    key_name VARCHAR(100) NOT NULL,
    api_key VARCHAR(100) UNIQUE NOT NULL,  -- Hashed
    api_secret_hash TEXT,  -- If using key + secret
    
    -- Permissions
    scopes VARCHAR(50)[],  -- ['read:tenders', 'write:favorites', 'read:alerts']
    
    -- Security
    allowed_ips INET[],
    rate_limit_per_hour INTEGER DEFAULT 1000,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP,
    use_count INTEGER DEFAULT 0,
    
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_api_keys_user ON user_api_keys(user_id);
CREATE INDEX idx_api_keys_key ON user_api_keys(api_key) WHERE is_active = TRUE;
```

### 3. Analytics & Usage Tracking

```sql
-- ============================================================================
-- USER ENGAGEMENT METRICS
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE analytics.user_engagement_daily (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_data.users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    
    -- Activity counts
    login_count INTEGER DEFAULT 0,
    search_count INTEGER DEFAULT 0,
    tender_views INTEGER DEFAULT 0,
    favorites_added INTEGER DEFAULT 0,
    alerts_triggered INTEGER DEFAULT 0,
    
    -- Session info
    total_session_duration_minutes INTEGER DEFAULT 0,
    
    -- Engagement score (calculated)
    engagement_score REAL,  -- Algorithm: weighted sum of activities
    
    UNIQUE(user_id, date)
);

CREATE INDEX idx_engagement_user ON analytics.user_engagement_daily(user_id, date DESC);
CREATE INDEX idx_engagement_date ON analytics.user_engagement_daily(date DESC);

-- ============================================================================
-- TENDER INTERACTION TRACKING
-- ============================================================================

CREATE TABLE analytics.tender_user_interactions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES user_data.users(id) ON DELETE SET NULL,
    tender_id INTEGER NOT NULL REFERENCES tender_data.tenders(id) ON DELETE CASCADE,
    
    interaction_type VARCHAR(50) NOT NULL,  -- 'view', 'favorite', 'note_add', 'share', 'download'
    
    -- Context
    source VARCHAR(50),  -- 'search', 'alert', 'recommendation', 'browse'
    device_type VARCHAR(20),  -- 'desktop', 'mobile', 'tablet'
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_interactions_user ON analytics.tender_user_interactions(user_id, created_at DESC);
CREATE INDEX idx_interactions_tender ON analytics.tender_user_interactions(tender_id);
CREATE INDEX idx_interactions_type ON analytics.tender_user_interactions(interaction_type, created_at DESC);
```

---

## User Authentication Implementation

### JWT-Based Authentication

```python
# backend/auth/jwt_handler.py
from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 30

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Generate JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    """Generate JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)

# backend/auth/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Dependency to get current authenticated user"""
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            credentials.credentials, 
            SECRET_KEY, 
            algorithms=[ALGORITHM]
        )
        user_id: int = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id is None or token_type != "access":
            raise credentials_exception
            
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.JWTError:
        raise credentials_exception
    
    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        raise credentials_exception
    
    if user.status != 'active':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active"
        )
    
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
):
    """Ensure user is active"""
    if current_user.status != "active":
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
```

### Authentication Endpoints

```python
# backend/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["authentication"])

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register new user"""
    
    # Check if email exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    
    user = User(
        email=user_data.email,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        phone=user_data.phone
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create default profile
    profile = UserProfile(user_id=user.id)
    db.add(profile)
    
    # Create default preferences
    preferences = UserPreferences(user_id=user.id)
    db.add(preferences)
    
    db.commit()
    
    # Generate tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    # Log activity
    activity = UserActivityLog(
        user_id=user.id,
        action_type="register",
        action_details={"method": "email"}
    )
    db.add(activity)
    db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "account_type": user.account_type
        }
    }

@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin, 
    db: Session = Depends(get_db),
    request: Request = None
):
    """Login existing user"""
    
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check account lock
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account locked until {user.locked_until}"
        )
    
    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        # Increment failed login attempts
        user.failed_login_attempts += 1
        user.last_failed_login = datetime.utcnow()
        
        # Lock account after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(hours=1)
        
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Successful login - reset failed attempts
    user.failed_login_attempts = 0
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = request.client.host if request else None
    db.commit()
    
    # Generate tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    # Log activity
    activity = UserActivityLog(
        user_id=user.id,
        action_type="login",
        ip_address=request.client.host if request else None
    )
    db.add(activity)
    db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "account_type": user.account_type
        }
    }

@router.post("/refresh")
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    """Get new access token using refresh token"""
    
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        token_type: str = payload.get("type")
        
        if token_type != "refresh":
            raise HTTPException(status_code=400, detail="Invalid token type")
        
        # Generate new access token
        new_access_token = create_access_token(data={"sub": user_id})
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout user (invalidate tokens)"""
    
    # Note: With JWT, we can't truly invalidate tokens server-side
    # Options:
    # 1. Maintain token blacklist in Redis
    # 2. Use short-lived access tokens (1 hour)
    # 3. Client-side token deletion
    
    # Log activity
    activity = UserActivityLog(
        user_id=current_user.id,
        action_type="logout"
    )
    db.add(activity)
    db.commit()
    
    return {"message": "Successfully logged out"}
```

---

## User Personalization Services

### 1. Favorites Management

```python
# backend/services/favorites_service.py
from sqlalchemy.orm import Session
from typing import List, Optional

class FavoritesService:
    """Manage user tender favorites"""
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
    
    async def add_favorite(
        self, 
        tender_id: int, 
        folder: Optional[str] = None,
        tags: List[str] = None,
        notes: Optional[str] = None,
        priority: str = 'medium'
    ):
        """Add tender to favorites"""
        
        # Check if already favorited
        existing = self.db.query(UserTenderFavorite).filter(
            UserTenderFavorite.user_id == self.user_id,
            UserTenderFavorite.tender_id == tender_id
        ).first()
        
        if existing:
            # Update existing
            if folder:
                existing.folder_name = folder
            if tags:
                existing.tags = tags
            if notes:
                existing.user_notes = notes
            existing.priority = priority
            existing.updated_at = datetime.utcnow()
        else:
            # Create new
            favorite = UserTenderFavorite(
                user_id=self.user_id,
                tender_id=tender_id,
                folder_name=folder,
                tags=tags,
                user_notes=notes,
                priority=priority
            )
            self.db.add(favorite)
        
        # Log activity
        activity = UserActivityLog(
            user_id=self.user_id,
            action_type="favorite_add",
            action_details={"tender_id": tender_id}
        )
        self.db.add(activity)
        
        self.db.commit()
        
        return {"message": "Added to favorites"}
    
    async def get_favorites(
        self, 
        folder: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ):
        """Get user's favorite tenders with full tender details"""
        
        query = self.db.query(
            UserTenderFavorite, 
            Tender
        ).join(
            Tender, 
            UserTenderFavorite.tender_id == Tender.id
        ).filter(
            UserTenderFavorite.user_id == self.user_id
        )
        
        if folder:
            query = query.filter(UserTenderFavorite.folder_name == folder)
        
        if priority:
            query = query.filter(UserTenderFavorite.priority == priority)
        
        favorites = query.order_by(
            UserTenderFavorite.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return [
            {
                "favorite_id": fav.UserTenderFavorite.id,
                "folder": fav.UserTenderFavorite.folder_name,
                "tags": fav.UserTenderFavorite.tags,
                "notes": fav.UserTenderFavorite.user_notes,
                "priority": fav.UserTenderFavorite.priority,
                "bid_status": fav.UserTenderFavorite.bid_status,
                "added_at": fav.UserTenderFavorite.created_at,
                "tender": {
                    "id": fav.Tender.id,
                    "tender_id": fav.Tender.tender_id_extracted,
                    "title": fav.Tender.title_ref,
                    "department": fav.Tender.department_name,
                    "closing_date": fav.Tender.closing_date_parsed,
                    "value": fav.Tender.tender_value_numeric,
                    "portal": fav.Tender.portal.name
                }
            }
            for fav in favorites
        ]
    
    async def update_bid_status(
        self, 
        favorite_id: int, 
        status: str,
        bid_amount: Optional[float] = None
    ):
        """Update bid status for a favorited tender"""
        
        favorite = self.db.query(UserTenderFavorite).filter(
            UserTenderFavorite.id == favorite_id,
            UserTenderFavorite.user_id == self.user_id
        ).first()
        
        if not favorite:
            raise ValueError("Favorite not found")
        
        favorite.bid_status = status
        
        if bid_amount:
            favorite.bid_amount = bid_amount
        
        if status == 'submitted':
            favorite.bid_submitted_at = datetime.utcnow()
        
        self.db.commit()
        
        return {"message": "Bid status updated"}
```

### 2. Smart Alerts Service

```python
# backend/services/alerts_service.py
import asyncio
from sqlalchemy.orm import Session
from typing import List, Dict

class AlertsService:
    """Manage user alerts and matching"""
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
    
    async def create_alert(
        self, 
        name: str,
        criteria: dict,
        notification_methods: List[str] = ['email'],
        frequency: str = 'immediate'
    ):
        """Create new alert"""
        
        # Validate criteria
        self._validate_criteria(criteria)
        
        alert = UserAlert(
            user_id=self.user_id,
            alert_name=name,
            criteria=criteria,
            notification_methods=notification_methods,
            notification_frequency=frequency
        )
        
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        
        # Immediate check for existing matches
        if frequency == 'immediate':
            await self.check_alert_matches(alert.id)
        
        return alert
    
    def _validate_criteria(self, criteria: dict):
        """Validate alert criteria structure"""
        # Add validation logic
        pass
    
    async def check_alert_matches(self, alert_id: int):
        """
        Check if any recent tenders match this alert
        Called by Celery task after new tenders are scraped
        """
        
        alert = self.db.query(UserAlert).filter(
            UserAlert.id == alert_id,
            UserAlert.is_active == True
        ).first()
        
        if not alert:
            return
        
        criteria = alert.criteria
        
        # Build query based on criteria
        query = self.db.query(Tender)
        
        # Keyword matching
        if 'keywords' in criteria:
            keywords = criteria['keywords']
            keyword_filter = or_(*[
                Tender.title_ref.ilike(f'%{kw}%') 
                for kw in keywords
            ])
            query = query.filter(keyword_filter)
        
        # Exclude keywords
        if 'exclude_keywords' in criteria:
            for exclude_kw in criteria['exclude_keywords']:
                query = query.filter(~Tender.title_ref.ilike(f'%{exclude_kw}%'))
        
        # State filter
        if 'states' in criteria:
            # Join with portal to get state
            query = query.join(Portal).filter(
                Portal.state.in_(criteria['states'])
            )
        
        # Value range
        if 'min_value' in criteria:
            query = query.filter(
                Tender.tender_value_numeric >= criteria['min_value']
            )
        if 'max_value' in criteria:
            query = query.filter(
                Tender.tender_value_numeric <= criteria['max_value']
            )
        
        # Closing date range
        if 'closing_date_range' in criteria:
            date_range = self._parse_date_range(criteria['closing_date_range'])
            query = query.filter(
                Tender.closing_date_parsed >= date_range['start'],
                Tender.closing_date_parsed <= date_range['end']
            )
        
        # Only check recent tenders (last 24 hours)
        last_check = alert.last_matched_at or (datetime.utcnow() - timedelta(days=1))
        query = query.filter(Tender.created_at > last_check)
        
        matches = query.all()
        
        if matches:
            # Create match records
            for tender in matches:
                match = UserAlertMatch(
                    alert_id=alert.id,
                    tender_id=tender.id,
                    notification_status='pending'
                )
                self.db.add(match)
            
            alert.total_matches += len(matches)
            alert.last_matched_at = datetime.utcnow()
            
            self.db.commit()
            
            # Queue notification
            if alert.notification_frequency == 'immediate':
                await self.send_alert_notifications(alert.id, matches)
        
        return len(matches)
    
    def _parse_date_range(self, range_str: str) -> dict:
        """Convert range string to date range"""
        today = datetime.utcnow().date()
        
        if range_str == 'next_7_days':
            return {'start': today, 'end': today + timedelta(days=7)}
        elif range_str == 'next_30_days':
            return {'start': today, 'end': today + timedelta(days=30)}
        elif range_str == 'this_week':
            # Implementation
            pass
        
        return {'start': today, 'end': today + timedelta(days=365)}
    
    async def send_alert_notifications(self, alert_id: int, tenders: List[Tender]):
        """Send notifications for matched tenders"""
        
        alert = self.db.query(UserAlert).filter(UserAlert.id == alert_id).first()
        user = self.db.query(User).filter(User.id == alert.user_id).first()
        
        # Check user preferences for quiet hours
        prefs = self.db.query(UserPreferences).filter(
            UserPreferences.user_id == user.id
        ).first()
        
        if self._is_quiet_hours(prefs):
            # Defer notification
            return
        
        # Send notifications based on methods
        for method in alert.notification_methods:
            if method == 'email':
                await self._send_email_notification(user, alert, tenders)
            elif method == 'sms':
                await self._send_sms_notification(user, alert, tenders)
            elif method == 'push':
                await self._send_push_notification(user, alert, tenders)
        
        # Update alert
        alert.last_notified_at = datetime.utcnow()
        alert.total_notifications_sent += 1
        
        # Update match records
        self.db.query(UserAlertMatch).filter(
            UserAlertMatch.alert_id == alert_id,
            UserAlertMatch.notification_status == 'pending'
        ).update({'notification_status': 'sent', 'notified_at': datetime.utcnow()})
        
        self.db.commit()
    
    async def _send_email_notification(self, user, alert, tenders):
        """Send email with matched tenders"""
        # Implementation using email service
        pass
```

### 3. Celery Task for Alert Matching

```python
# backend/tasks/alert_matcher.py
from celery import shared_task
from sqlalchemy.orm import Session

@shared_task
def check_all_alerts_after_scrape(portal_id: int, run_id: int):
    """
    After a scraping run completes, check all active alerts
    for matches with new tenders
    """
    
    db = SessionLocal()
    
    try:
        # Get all active alerts
        alerts = db.query(UserAlert).filter(
            UserAlert.is_active == True
        ).all()
        
        logger.info(f"Checking {len(alerts)} alerts for new matches from run {run_id}")
        
        for alert in alerts:
            alerts_service = AlertsService(db, alert.user_id)
            matches = await alerts_service.check_alert_matches(alert.id)
            
            if matches:
                logger.info(f"Alert {alert.id} matched {matches} new tenders")
        
    finally:
        db.close()

@shared_task
def send_daily_alert_digest():
    """
    Send daily digest emails to users who prefer digest mode
    """
    
    db = SessionLocal()
    
    try:
        # Get users with daily digest preference
        users = db.query(User).join(UserPreferences).filter(
            UserPreferences.email_digest_frequency == 'daily'
        ).all()
        
        for user in users:
            # Get unnotified matches from last 24 hours
            matches = db.query(UserAlertMatch).join(UserAlert).filter(
                UserAlert.user_id == user.id,
                UserAlertMatch.notification_status == 'pending',
                UserAlertMatch.matched_at >= datetime.utcnow() - timedelta(days=1)
            ).all()
            
            if matches:
                # Send digest email
                await send_digest_email(user, matches)
                
                # Update notification status
                for match in matches:
                    match.notification_status = 'sent'
                    match.notified_at = datetime.utcnow()
                
                db.commit()
    
    finally:
        db.close()
```

---

## Multi-Tenancy (Organization Support)

### Organization-Level Features

```python
# backend/services/organization_service.py
class OrganizationService:
    """Manage organization accounts and team collaboration"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_organization(
        self, 
        owner_user_id: int,
        name: str,
        subscription_plan: str = 'team'
    ):
        """Create new organization"""
        
        org = Organization(
            name=name,
            subscription_plan=subscription_plan,
            max_users=self._get_plan_limits(subscription_plan)['max_users']
        )
        
        self.db.add(org)
        self.db.commit()
        self.db.refresh(org)
        
        # Add owner as first member
        member = OrganizationUser(
            organization_id=org.id,
            user_id=owner_user_id,
            role='owner'
        )
        self.db.add(member)
        self.db.commit()
        
        return org
    
    async def invite_member(
        self, 
        org_id: int, 
        inviter_user_id: int,
        invitee_email: str,
        role: str = 'member'
    ):
        """Invite user to organization"""
        
        # Check inviter permissions
        inviter = self.db.query(OrganizationUser).filter(
            OrganizationUser.organization_id == org_id,
            OrganizationUser.user_id == inviter_user_id,
            OrganizationUser.role.in_(['owner', 'admin'])
        ).first()
        
        if not inviter:
            raise PermissionError("Only owners/admins can invite members")
        
        # Check organization limits
        org = self.db.query(Organization).filter(Organization.id == org_id).first()
        current_members = self.db.query(OrganizationUser).filter(
            OrganizationUser.organization_id == org_id
        ).count()
        
        if current_members >= org.max_users:
            raise ValueError(f"Organization has reached max users limit ({org.max_users})")
        
        # Check if user exists
        invitee = self.db.query(User).filter(User.email == invitee_email).first()
        
        if invitee:
            # Add directly
            member = OrganizationUser(
                organization_id=org_id,
                user_id=invitee.id,
                role=role
            )
            self.db.add(member)
            self.db.commit()
        else:
            # Send invitation email
            # Store pending invitation
            pass
        
        return {"message": "Invitation sent"}
    
    async def get_shared_favorites(self, org_id: int, user_id: int):
        """Get favorites shared within organization"""
        
        # Verify user is org member
        member = self.db.query(OrganizationUser).filter(
            OrganizationUser.organization_id == org_id,
            OrganizationUser.user_id == user_id
        ).first()
        
        if not member:
            raise PermissionError("User not part of this organization")
        
        # Get all org members
        org_user_ids = [
            m.user_id 
            for m in self.db.query(OrganizationUser).filter(
                OrganizationUser.organization_id == org_id
            ).all()
        ]
        
        # Get shared favorites
        favorites = self.db.query(
            UserTenderFavorite, 
            Tender,
            User
        ).join(
            Tender
        ).join(
            User, UserTenderFavorite.user_id == User.id
        ).filter(
            UserTenderFavorite.user_id.in_(org_user_ids),
            # Add sharing flag when implemented
        ).all()
        
        return favorites
```

---

## Session & Cache Management

### Redis for Session Storage

```python
# backend/cache/redis_manager.py
import redis
import json
from typing import Optional

class RedisSessionManager:
    """Manage user sessions in Redis"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_SESSION_DB,
            decode_responses=True
        )
    
    def store_session(self, user_id: int, session_data: dict, ttl: int = 3600):
        """Store user session data"""
        key = f"session:{user_id}"
        self.redis_client.setex(
            key,
            ttl,
            json.dumps(session_data)
        )
    
    def get_session(self, user_id: int) -> Optional[dict]:
        """Get user session data"""
        key = f"session:{user_id}"
        data = self.redis_client.get(key)
        return json.loads(data) if data else None
    
    def delete_session(self, user_id: int):
        """Delete user session (logout)"""
        key = f"session:{user_id}"
        self.redis_client.delete(key)
    
    def cache_user_preferences(self, user_id: int, preferences: dict):
        """Cache frequently accessed user preferences"""
        key = f"user_prefs:{user_id}"
        self.redis_client.setex(key, 3600, json.dumps(preferences))
    
    def get_cached_preferences(self, user_id: int) -> Optional[dict]:
        """Get cached user preferences"""
        key = f"user_prefs:{user_id}"
        data = self.redis_client.get(key)
        return json.loads(data) if data else None
```

---

## API Endpoints: User Features

```python
# backend/api/user_features.py
from fastapi import APIRouter, Depends
from typing import List, Optional

router = APIRouter(prefix="/user", tags=["user_features"])

# ============================================================================
# FAVORITES
# ============================================================================

@router.post("/favorites")
async def add_favorite(
    tender_id: int,
    folder: Optional[str] = None,
    tags: List[str] = [],
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add tender to favorites"""
    service = FavoritesService(db, current_user.id)
    return await service.add_favorite(tender_id, folder, tags, notes)

@router.get("/favorites")
async def get_favorites(
    folder: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's favorites"""
    service = FavoritesService(db, current_user.id)
    return await service.get_favorites(folder, priority, limit, offset)

@router.delete("/favorites/{favorite_id}")
async def remove_favorite(
    favorite_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove from favorites"""
    db.query(UserTenderFavorite).filter(
        UserTenderFavorite.id == favorite_id,
        UserTenderFavorite.user_id == current_user.id
    ).delete()
    db.commit()
    return {"message": "Removed from favorites"}

# ============================================================================
# ALERTS
# ============================================================================

@router.post("/alerts")
async def create_alert(
    name: str,
    criteria: dict,
    notification_methods: List[str] = ['email'],
    frequency: str = 'immediate',
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new alert"""
    service = AlertsService(db, current_user.id)
    return await service.create_alert(name, criteria, notification_methods, frequency)

@router.get("/alerts")
async def get_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all user alerts"""
    alerts = db.query(UserAlert).filter(
        UserAlert.user_id == current_user.id
    ).all()
    return alerts

@router.patch("/alerts/{alert_id}")
async def update_alert(
    alert_id: int,
    is_active: Optional[bool] = None,
    criteria: Optional[dict] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update alert settings"""
    alert = db.query(UserAlert).filter(
        UserAlert.id == alert_id,
        UserAlert.user_id == current_user.id
    ).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    if is_active is not None:
        alert.is_active = is_active
    if criteria:
        alert.criteria = criteria
    
    db.commit()
    return alert

# ============================================================================
# SAVED SEARCHES
# ============================================================================

@router.post("/saved-searches")
async def save_search(
    name: str,
    query: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save a search for quick access"""
    saved_search = UserSavedSearch(
        user_id=current_user.id,
        search_name=name,
        search_query=query
    )
    db.add(saved_search)
    db.commit()
    return saved_search

# ============================================================================
# NOTIFICATIONS
# ============================================================================

@router.get("/notifications")
async def get_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user notifications"""
    query = db.query(UserNotification).filter(
        UserNotification.user_id == current_user.id
    )
    
    if unread_only:
        query = query.filter(UserNotification.is_read == False)
    
    notifications = query.order_by(
        UserNotification.created_at.desc()
    ).limit(limit).all()
    
    return notifications

@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark notification as read"""
    notification = db.query(UserNotification).filter(
        UserNotification.id == notification_id,
        UserNotification.user_id == current_user.id
    ).first()
    
    if notification:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.commit()
    
    return {"message": "Marked as read"}
```

---

## Performance Considerations

### 1. Database Indexing Strategy

```sql
-- Critical indexes for user queries

-- Favorites: Most common query pattern
CREATE INDEX idx_favorites_user_created 
ON user_tender_favorites(user_id, created_at DESC);

-- Alerts: Active alerts need fast lookup
CREATE INDEX idx_alerts_active_user 
ON user_alerts(user_id, is_active) WHERE is_active = TRUE;

-- Notifications: Unread notifications
CREATE INDEX idx_notifications_user_unread 
ON user_notifications(user_id, is_read) WHERE is_read = FALSE;

-- Activity log: Recent activity
CREATE INDEX idx_activity_user_recent 
ON user_activity_log(user_id, created_at DESC);

-- Alert matches: Pending notifications
CREATE INDEX idx_alert_matches_pending 
ON user_alert_matches(notification_status, matched_at DESC) 
WHERE notification_status = 'pending';
```

### 2. Caching Strategy

```python
# Cache hot data in Redis

# User preferences (accessed on every request)
CACHE_DURATION_PREFERENCES = 3600  # 1 hour

# Alert criteria (checked on every new tender)
CACHE_DURATION_ALERTS = 1800  # 30 minutes

# User profile data
CACHE_DURATION_PROFILE = 7200  # 2 hours

# Implementation
@cache_in_redis(ttl=3600)
def get_user_preferences(user_id: int):
    return db.query(UserPreferences).filter(
        UserPreferences.user_id == user_id
    ).first()
```

### 3. Alert Matching Optimization

```python
# Use materialized view for active alerts
CREATE MATERIALIZED VIEW mv_active_alerts AS
SELECT 
    id,
    user_id,
    criteria,
    notification_methods,
    notification_frequency
FROM user_alerts
WHERE is_active = TRUE;

CREATE INDEX idx_mv_active_alerts ON mv_active_alerts(id);

# Refresh hourly
-- Celery task
@periodic_task(run_every=crontab(minute=0))
def refresh_active_alerts_view():
    db.execute("REFRESH MATERIALIZED VIEW mv_active_alerts")
```

---

## Security Best Practices

### 1. Password Requirements

```python
def validate_password(password: str) -> bool:
    """
    Enforce strong password policy:
    - Min 8 characters
    - At least 1 uppercase, 1 lowercase, 1 digit, 1 special char
    """
    if len(password) < 8:
        return False
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in '!@#$%^&*()_+-=' for c in password)
    
    return has_upper and has_lower and has_digit and has_special
```

### 2. Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("5/minute")  # Max 5 login attempts per minute
async def login(request: Request, ...):
    # Implementation
    pass

@router.post("/alerts")
@limiter.limit("20/hour")  # Max 20 alert creations per hour
async def create_alert(request: Request, ...):
    # Implementation
    pass
```

### 3. Data Privacy

```python
# Never expose sensitive data in API responses
class UserProfileResponse(BaseModel):
    """Safe user profile response (exclude sensitive fields)"""
    id: int
    full_name: str
    company_name: Optional[str]
    
    # Exclude:
    # - gst_number, pan_number (PII)
    # - email (unless own profile)
    # - phone (unless own profile)
    
    class Config:
        orm_mode = True
```

---

## Migration from v2.2.1

### Data Migration Script

```python
# migrations/migrate_user_data.py
"""
Migrate existing user patterns to new user system
"""

def migrate_existing_usage_patterns():
    """
    If v2.2.1 had any implicit user patterns (e.g., saved Excel locations),
    migrate them to new user preferences
    """
    
    # Example: If there were saved portal preferences in config
    old_config = load_old_config()
    
    # Create default admin user
    admin_user = create_admin_user()
    
    # Migrate portal preferences to user preferences
    migrate_portal_preferences(old_config, admin_user.id)
    
    # Create default alerts based on frequently used searches
    migrate_common_searches_to_alerts(admin_user.id)
```

---

## Summary: Database Strategy

### ✅ Use Single PostgreSQL Database

**Benefits:**
1. **Simpler management** - One backup, one connection pool
2. **ACID transactions** - User actions + tender updates in single transaction
3. **Efficient queries** - Join user favorites with tender details easily
4. **Lower cost** - One database instance vs multiple
5. **Easier scaling** - PostgreSQL handles millions of rows no problem

**Separation via:**
- Schemas: `user_data`, `tender_data`, `analytics`
- Clear table naming: `user_*`, `tender_*`, `portal_*`
- Service layer: UserService, TenderService kept separate in code

**When to consider separate databases:**
- **Scale >10M users** - Then split for horizontal sharding
- **Compliance requirements** - If user PII must be isolated
- **Independent scaling** - If user service needs different resources

For your scale (100-1000s of users initially), **single database is optimal**.

---

**You now have a complete user management system** with accounts, profiles, favorites, smart alerts, saved searches, notifications, organizations, and API access! 🎯