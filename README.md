# Secure File Sharing and Recovery System (Lazarus)

## Project Overview

Lazarus is a Flask-based secure file sharing and recovery system. Uploaded files are encrypted, fragmented using erasure coding, stored across separate OCI Object Storage buckets, and reconstructed only when the required number of valid fragments is available.

The system is designed so that complete readable files are not stored directly after processing. MySQL stores metadata, while encrypted fragments are stored in storage nodes represented by OCI buckets.

## Technology Stack

### Frontend

* HTML
* CSS
* JavaScript
* Bootstrap

### Backend

* Python
* Flask
* Gunicorn for server execution on the OCI compute instance

### Database

* MySQL

### Cloud and Storage

* Oracle Cloud Infrastructure (OCI)
* OCI Compute instance for hosting the Flask application
* OCI Object Storage buckets as storage nodes for encrypted fragments
* OCI Python SDK for bucket operations

### Security and Recovery Technologies

* AES-256-GCM encryption and decryption
* zfec erasure coding for file fragmentation and reconstruction
* bcrypt password hashing
* Environment-based master key for protecting per-file encryption keys

## System Architecture

The system follows a BCE-aligned Flask structure:

1. Boundary

   * HTML templates and JavaScript-driven user interactions

2. Control

   * Flask controller files under `controllers/`
   * Controllers receive requests, coordinate entities, and return pages or JSON responses

3. Entity

   * Database-backed and storage-backed entity files under `entities/`
   * Entity classes handle database operations, encryption, fragmentation, storage access, and metadata retrieval according to their responsibility

## Storage Architecture

Processed files are encrypted and split into fragments before storage. Each fragment is stored in a different active storage node where possible.

In the deployed version, each storage node is represented by an OCI Object Storage bucket. The `storage_nodes` table stores node metadata such as node name, bucket name, and node status. The `fragments` table stores fragment metadata such as file ID, fragment number, node ID, object path, and fragment status.

The application uses the OCI Python SDK with instance principal authentication to upload, retrieve, and delete fragment objects from OCI buckets.

## Encryption Key Handling

Each uploaded file is encrypted using a generated AES-256-GCM file key and nonce. The file key is wrapped using a deployment master key stored outside the database as the `LAZARUS_MASTER_KEY` environment variable.

This means MySQL stores the encrypted file key, not the raw file key. The nonce and encrypted key metadata are stored with the file record so the system can later reconstruct and decrypt the file.

## Deployment

The application is deployed on an OCI Compute instance. The Flask application is run through Gunicorn and managed using a systemd service so that the application can restart automatically when the server reboots.

The deployed service requires the following environment variables to be available to the running application:

* `LAZARUS_MASTER_KEY`
* Database connection settings used by `db.py`
* OCI instance principal permissions for Object Storage access

## Seeded User Accounts

The following accounts are available for testing purposes:

| Username  | Role         |
| --------- | ------------ |
| demo      | User         |
| johnsmith | User         |
| admin     | User Admin   |
| sysadmin  | System Admin |

For seeded testing accounts, the default password follows the project seed data used in `create.sql`.

## Running the Application Locally

1. Execute `create.sql` to create the database and seed the sample data.
2. Install required dependencies:

```bash
pip install -r requirements.txt
```

3. Set the required environment variables, including `LAZARUS_MASTER_KEY`.
4. Start the application:

```bash
python app.py
```

5. Open:

```text
http://127.0.0.1:5000
```
