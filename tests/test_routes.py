"""
Account API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
"""
import os
import logging
from unittest import TestCase
from tests.factories import AccountFactory
from service.common import status  # HTTP Status Codes
from service.models import db, Account, init_db
from service.routes import app
from service import talisman

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)

BASE_URL = "/accounts"
HTTPS_ENVIRON = {'wsgi.url_scheme': 'https'}


######################################################################
#  T E S T   C A S E S
######################################################################
class TestAccountService(TestCase):
    """Account Service Tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)
        talisman.force_https = False

    @classmethod
    def tearDownClass(cls):
        """Runs once before test suite"""

    def setUp(self):
        """Runs before each test"""
        db.session.query(Account).delete()  # clean up the last tests
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        """Runs once after each test case"""
        db.session.remove()

    ######################################################################
    #  H E L P E R   M E T H O D S
    ######################################################################

    def _create_accounts(self, count):
        """Factory method to create accounts in bulk"""
        accounts = []
        for _ in range(count):
            account = AccountFactory()
            response = self.client.post(BASE_URL, json=account.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test Account",
            )
            new_account = response.get_json()
            account.id = new_account["id"]
            accounts.append(account)
        return accounts

    ######################################################################
    #  A C C O U N T   T E S T   C A S E S
    ######################################################################

    def test_index_cors(self, environ_overrides=HTTPS_ENVIRON):
        """It should return a reply with CORS headers"""
        cors = {"Access-Control-Allow-Origin": "*"}
        response = self.client.get("/")
        logging.debug(response.__dict__)
        for i in cors:
            r = response.headers.get(i)
            self.assertIsNotNone(r)
            self.assertEqual(cors[i], r)

    def test_index_environ(self, environ_overrides=HTTPS_ENVIRON):
        """It should return specified security headers"""
        headers = {
            'X-Frame-Options': 'SAMEORIGIN',
            'X-Content-Type-Options': 'nosniff',
            'Content-Security-Policy': 'default-src \'self\'; object-src \'none\'',
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        }
        response = self.client.get("/")
        logging.debug(response.__dict__)
        for i in headers:
            r = response.headers.get(i)
            self.assertIsNotNone(r)
            self.assertEqual(headers[i], r)

    def test_index(self):
        """It should get 200_OK from the Home Page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health(self):
        """It should be healthy"""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "OK")

    def test_create_account(self):
        """It should Create a new Account"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_account = response.get_json()
        self.assertEqual(new_account["name"], account.name)
        self.assertEqual(new_account["email"], account.email)
        self.assertEqual(new_account["address"], account.address)
        self.assertEqual(new_account["phone_number"], account.phone_number)
        self.assertEqual(new_account["date_joined"], str(account.date_joined))

    def test_bad_request(self):
        """It should not Create an Account when sending the wrong data"""
        response = self.client.post(BASE_URL, json={"name": "not enough data"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_media_type(self):
        """It should not Create an Account when sending the wrong media type"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="test/html"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_read_an_account(self):
        """It should read an account"""

        # create a new account
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # obtain the new account
        new_account = response.get_json()
        new_response = self.client.get(BASE_URL+f'/{new_account["id"]}')
        self.assertEqual(new_response.status_code, status.HTTP_200_OK)

        # check response data from account creation is equal to
        # it's read content
        self.assertEqual(new_response.get_json(), response.get_json())

    def test_account_not_found(self):
        """It should result in an 404 not found on account read"""
        non_existing_id = 0
        response = self.client.get(BASE_URL+f'/{non_existing_id}')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_accounts(self):
        """It should result in a 200 OK and a retrieval of all accounts"""

        # tests if [] is returned since no accounts should exist
        response = self.client.get(BASE_URL)
        message = response.get_json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(message, [])

        # creates N [1-10] accounts
        import random
        n_accounts = random.randint(1, 10)
        accounts = [AccountFactory() for x in range(n_accounts)]
        for _, account in enumerate(accounts):
            response = self.client.post(
                BASE_URL,
                json=account.serialize(),
                content_type="application/json"
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # tests if the service returns N accounts
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        message = response.get_json()
        self.assertEqual(len(message), n_accounts)

    def test_updates_existing_account(self):
        """It should result in 200 ok and account data should be updated"""

        # create a new account instance
        account = AccountFactory()
        # request update on this account without creating it firstly
        response = self.client.put(BASE_URL+f'/{account.id}', json=account.serialize())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # create this account remotely
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # update account
        name = 'MR random'
        address = 'rand Random BLV'

        original_account = response.get_json()
        new_account = original_account.copy()
        new_account['name'] = name
        new_account['address'] = address

        # request account update
        message = new_account
        response = self.client.put(BASE_URL+f'/{new_account["id"]}', json=message)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_account = response.get_json()

        self.assertEqual(response_account["name"], name)
        self.assertEqual(response_account["address"], address)

    def test_delete_account(self):
        """It should result in 204 no content upon account deletion"""

        # create a new account
        account = AccountFactory()

        # attempt to delete it on the remote service
        response = self.client.delete(
            BASE_URL+f'/{account.id}',
            json=account.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # check the account does not exist
        new_response = self.client.get(BASE_URL+f'/{account.id}')
        self.assertEqual(new_response.status_code, status.HTTP_404_NOT_FOUND)

        # create the account remotely
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.delete(
            BASE_URL+f'/{account.id}',
            json=account.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # check again the account does not exist
        new_response = self.client.get(BASE_URL+f'/{account.id}')
        self.assertEqual(new_response.status_code, status.HTTP_404_NOT_FOUND)
