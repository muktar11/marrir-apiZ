# PATH SIN API

## Details about project

### Dependencies & Concepts to learn about

* Fast API
* SQLAlchemy
    * ORM
    * Core
* Docker
* Make
* Abstract Repository Pattern

### Styles

* PEP 8
* case
    * snake_case
        * database
        * api_responses
    * PascalCase
        * ClassNames
        * Constants

### Project Specific Details

* Context variables are used for various aspects of the project, managing dependencies around the project.
* Documentation for swagger can be found @ URL/docs -> e.g. -> http://localhost:8000/docs

* Response Methods and Codes might not adhere to http best practices, but there is method to the madness
    * DELETEs are normally associated with 204 response code, but 204 can not have a response body according to
      starlette, therefore 200 was used
        * It is essential that deletes return the refreshed entity to simplify the work on the frontend

* Every protected resource will require either a hybrid property that returns an owner id or have an owner id.
    * The owner id will be the email of the user who created the resource and will enforce owner security on resources.

# Logs

* path_sin_api logs will follow the format based on the custom logger
    * %(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)
* fast_api logs will follow the following format
    * %(asctime)s - %(name)s - %(levelname)s - %(message)s

# Tests

## General

* Make sure to name tests alphabetically
    * The format followed in the user resource test file is
        * {test}_{alpha}_{name_of_controller}
            * see user resource test as an example
* No mocks or patches are used thus far, but may be needed as you integrate more features
    * [look here for details](https://realpython.com/python-mock-library/#what-is-mocking)

## UnitTests

* Uses fastapi testing library

## PerformanceTests

* Uses locust testing library
* Steps
    * run make script ```make perf_test```
    * web portal for configuring the performance test should be available @[http://localhost:8089](http:localhost:8089)
      by default

* Route Handlers should be async, as await errors might occur
* The authorization handler will have to be invoked as a decorator as it requires extra arguments


# Passport Scanning

To make use of the passport scanning feature, you will need to have the following install `tesseract-ocr`:

```bash
sudo apt-get install tesseract-ocr
```

For Mac users, you can install it using `brew`:

```bash
brew install tesseract
```

For Windows users, after installing `tesseract-ocr`, you will need to add the path, so that the your python script can work:

```python
import pytesseract

# Specify the path to the Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```
#   m a r r i r - u s e  
 #   m a r r i r - u s e  
 #   m a r r i r - u s e  
 #   m a r r i r - a p i  
 #   m a r r i r - a p i  
 #   m a r r i r - a p i  
 #   m a r r i r - a p i  
 #   m a r r i r - a p i  
 #   m a r r i r - a p i  
 #   m  
 #   m  
 #   m  
 #   m a r r i r - a p i  
 #   m a r r i r - a p i Z  
 #   m a r r i r - a p i Z  
 