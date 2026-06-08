# Secure File Sharing and Recovery System (SFSRS)

## Project Overview

The Secure File Sharing and Recovery System (SFSRS) is a web-based application developed as a Final Year Project (FYP). The system aims to provide secure file upload, storage, sharing, and recovery through the use of encryption and file fragmentation techniques.

Users will be able to upload files, configure reconstruction settings, securely share files with other users, and recover files when the required number of fragments is available.

## Technology Stack

### Frontend

* HTML
* CSS
* JavaScript
* Bootstrap

### Backend

* Python
* Flask

### Database

* MySQL

### Security Technologies

* AES-256-GCM (Planned)
* Reed-Solomon Erasure Coding (Planned)

## System Architecture

The system follows a three-tier architecture:

1. Presentation Layer

   * HTML, CSS, JavaScript, Bootstrap

2. Application Layer

   * Flask backend
   * Business logic
   * File processing

3. Data Layer

   * MySQL database
   * Temporary file storage
   * Simulated storage nodes

## Seeded User Accounts

The following accounts are available for testing purposes:

| Username  | Role         |
| --------- | ------------ |
| demo      | User         |
| johnsmith | User         |
| admin     | User Admin   |
| sysadmin  | System Admin |

Note: Authentication functionality is currently under development. These accounts are provided as seeded database records for testing.

## Running the Application

1. Execute `create.sql` to create the database and seed the sample data.
2. Install required dependencies:

```bash
pip install flask mysql-connector-python werkzeug
```

3. Start the application:

```bash
python app.py
```

4. Open:

```text
http://127.0.0.1:5000
```
