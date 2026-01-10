# Asset Distribution System

A Django web application for managing fair distribution of estate assets among family members.

## Features

- **Family Structure**: Supports 3 family branches with customizable member lists
- **Asset Management**: Upload and categorize assets with photos
- **Interest Tracking**: Family members express interest and rank desired items
- **Legacy Priority Round**: Special round for sentimental must-have items
- **Fair Distribution**: Randomized turn order ensures equitable distribution across branches
- **Admin Control**: Full administrative control over the distribution process

## Quick Start

### 1. Set Up Python Environment

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
# Run migrations
python manage.py makemigrations core
python manage.py migrate

# Set up initial data (family members, categories, passwords)
python manage.py setup_initial_data
```

### 3. Run Development Server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000` in your browser.

## Default Passwords

| Type | Password |
|------|----------|
| Family | `` |
| Admin | `` |

**⚠️ Change these immediately after first login!**

## Usage

### For Family Members

1. Enter the family password
2. Select your name from the list
3. Browse assets and click "I Want This" on items you want
4. Rank your interests (lower number = higher priority)
5. When Legacy Round is active, submit your Top 3 must-have items

### For Administrators

1. Log in with the admin password
2. Upload assets with photos
3. Set the distribution phase
4. Run the Legacy Round and resolve conflicts
5. For Category Distribution:
   - Select a category
   - Randomize branch order
   - Assign items based on turn order and interests

## Distribution Logic

### Family Structure
- **Branch A (Lynn)**: Father + 6 children
- **Branch B (Richard)**: Father + 6 children  
- **Branch C (Rob)**: 2 children representing their deceased father

### Turn Order Rules
- Each category has a randomized branch order
- Within Branches A & B: Father picks first and last, children randomized in between
- Branch C: Brian and Michael alternate to fill equivalent slots
- If someone passes, their pick reverts to the branch father (preserves 1/3 share)

## Deployment to PythonAnywhere

1. Upload project files to PythonAnywhere
2. Create a virtual environment and install requirements
3. Set `DEBUG = False` in settings.py
4. Configure ALLOWED_HOSTS with your domain
5. Set up static and media file serving
6. Run migrations and setup_initial_data
7. Configure WSGI file

## Project Structure

```
asset_distribution/
├── manage.py
├── requirements.txt
├── asset_distribution/      # Django project settings
├── core/                    # Main application
│   ├── models.py           # Database models
│   ├── views.py            # View logic
│   ├── forms.py            # Form definitions
│   ├── urls.py             # URL routing
│   └── management/         # Custom management commands
├── templates/               # HTML templates
├── static/                  # CSS, JS, images
└── media/                   # Uploaded photos
```

## License

Private use only.
