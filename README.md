# SevenPastel POS System

This is a simple Point of Sale (POS) system built using Flask, SQLite, and basic HTML/CSS/JavaScript.

## Features

*   **Product Management**: Add, view, edit, and delete products.
*   **Point of Sale Interface**: A basic interface to add products to a cart and calculate the total.
*   **SQLite Database**: Uses a SQLite database for data persistence.

## Setup Instructions

1.  **Clone the repository (or extract the zip file)**:

    ```bash
    # If it were a git repository
    # git clone <repository_url>
    # cd pos_sevenpastel_clean
    ```

2.  **Create a Python Virtual Environment** (recommended):

    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

4.  **Initialize the Database**:

    The application uses a `schema.sql` file to set up the database. This will be created in a later step.

    You can initialize the database by running a Python interpreter within the project directory:

    ```python
    from app import app, init_db
    with app.app_context():
        init_db()
    ```

## Running the Application

To run the Flask application, navigate to the `pos_sevenpastel_clean` directory in your terminal and execute:

```bash
flask run
```

Alternatively, if you've activated your virtual environment and are in the project root:

```bash
python app.py
```

The application will typically be available at `http://127.0.0.1:5000/`.
