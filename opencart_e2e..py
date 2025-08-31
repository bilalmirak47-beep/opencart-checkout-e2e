# opencart_e2e.py
# One-file Selenium (Python) E2E for OpenCart demo:
# Signup -> Login -> Dashboard verify -> Add to Cart -> View Cart -> Checkout
# Uses: OOP (inheritance), polymorphism (checkout steps), and webdriver-manager.

from __future__ import annotations
from dataclasses import dataclass
from abc import ABC, abstractmethod
import time
from typing import Tuple, List

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from faker import Faker


BASE_URL = "https://demo.opencart.com/"

# ------------- Base Layer (Inheritance) -----------------
class BasePage:
    def __init__(self, driver, timeout: int = 12):
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)

    def open(self, url: str):
        self.driver.get(url)

    def find(self, locator: Tuple[By, str]):
        return self.wait.until(EC.visibility_of_element_located(locator))

    def click(self, locator: Tuple[By, str]):
        self.wait.until(EC.element_to_be_clickable(locator)).click()

    def type(self, locator: Tuple[By, str], text: str, clear: bool = True):
        el = self.find(locator)
        if clear:
            el.clear()
        el.send_keys(text)

    def text_of(self, locator: Tuple[By, str]) -> str:
        return self.find(locator).text

    def exists(self, locator: Tuple[By, str], quick: bool = True) -> bool:
        try:
            WebDriverWait(self.driver, 3 if quick else 10).until(
                EC.presence_of_element_located(locator)
            )
            return True
        except TimeoutException:
            return False


# ------------- Page Objects -----------------
class HomePage(BasePage):
    MY_ACCOUNT = (By.CSS_SELECTOR, "a[title='My Account']")
    REGISTER = (By.CSS_SELECTOR, "a[href*='route=account/register']")
    LOGIN = (By.CSS_SELECTOR, "a[href*='route=account/login']")
    SEARCH_INPUT = (By.NAME, "search")
    SEARCH_BTN = (By.CSS_SELECTOR, "#search button")

    def go_register(self):
        self.click(self.MY_ACCOUNT)
        self.click(self.REGISTER)

    def go_login(self):
        self.click(self.MY_ACCOUNT)
        self.click(self.LOGIN)

    def search(self, query: str):
        self.type(self.SEARCH_INPUT, query)
        self.click(self.SEARCH_BTN)


class RegisterPage(BasePage):
    FIRST = (By.ID, "input-firstname")
    LAST = (By.ID, "input-lastname")
    EMAIL = (By.ID, "input-email")
    PHONE = (By.ID, "input-telephone")
    PASS = (By.ID, "input-password")
    CONF = (By.ID, "input-confirm")
    POLICY = (By.NAME, "agree")
    CONTINUE = (By.CSS_SELECTOR, "input[value='Continue'], button[type='submit']")

    def register(self, first, last, email, phone, password):
        self.type(self.FIRST, first)
        self.type(self.LAST, last)
        self.type(self.EMAIL, email)
        self.type(self.PHONE, phone)
        self.type(self.PASS, password)
        self.type(self.CONF, password)
        # Some demo themes place the checkbox out of view; make sure it’s clickable.
        try:
            self.click(self.POLICY)
        except TimeoutException:
            self.driver.execute_script("arguments[0].click();", self.find(self.POLICY))
        self.click(self.CONTINUE)


class LoginPage(BasePage):
    EMAIL = (By.ID, "input-email")
    PASS = (By.ID, "input-password")
    LOGIN_BTN = (By.CSS_SELECTOR, "input[value='Login'], button[type='submit']")

    def login(self, email, password):
        self.type(self.EMAIL, email)
        self.type(self.PASS, password)
        self.click(self.LOGIN_BTN)


class AccountDashboardPage(BasePage):
    BREADCRUMB_LAST = (By.CSS_SELECTOR, ".breadcrumb li:last-child")
    LOGOUT = (By.CSS_SELECTOR, "a[href*='route=account/logout']")

    def is_loaded(self) -> bool:
        try:
            return "Account" in self.text_of(self.BREADCRUMB_LAST)
        except TimeoutException:
            return False

    def logout(self):
        self.click(self.LOGOUT)


class ProductPage(BasePage):
    # From search/list page:
    FIRST_RESULT = (By.CSS_SELECTOR, ".product-thumb h4 a, .product-layout h4 a")
    ADD_TO_CART = (By.CSS_SELECTOR, "#button-cart, button#button-cart, button[onclick*='cart.add']")

    def open_first_result(self):
        self.click(self.FIRST_RESULT)

    def add_to_cart(self):
        # On listing page, sometimes there’s a direct add button; otherwise open PDP then add.
        if self.exists(self.ADD_TO_CART) and "cart.add" in self.find(self.ADD_TO_CART).get_attribute("onclick") if self.exists(self.ADD_TO_CART) else False:
            self.click(self.ADD_TO_CART)
        else:
            # ensure we’re on PDP
            if self.exists(self.FIRST_RESULT):
                self.click(self.FIRST_RESULT)
            self.click(self.ADD_TO_CART)
        # tiny wait for mini-toast
        time.sleep(1)


class CartPage(BasePage):
    CART_LINK = (By.CSS_SELECTOR, "a[href*='route=checkout/cart'], a[title='Shopping Cart']")
    CHECKOUT_BTN = (By.CSS_SELECTOR, "a[href*='route=checkout/checkout'], .pull-right a.btn-primary, a.btn-primary")

    def open_cart(self):
        self.click(self.CART_LINK)

    def proceed_to_checkout(self):
        self.click(self.CHECKOUT_BTN)


class CheckoutPage(BasePage):
    SUCCESS_HEADER = (By.CSS_SELECTOR, "#content h1, .checkout-success h1")

    def success_message(self) -> str:
        return self.text_of(self.SUCCESS_HEADER)


# ------------- Polymorphism: checkout steps share same interface -------------
class CheckoutStep(BasePage, ABC):
    @abstractmethod
    def perform(self): ...


class BillingStep(CheckoutStep):
    # IDs vary across themes; we try common ones.
    CONTINUE = (By.ID, "button-payment-address")
    ALT_CONTINUE = (By.ID, "button-payment-address")  # kept for readability

    def perform(self):
        self._click_any([self.CONTINUE, self.ALT_CONTINUE])

    def _click_any(self, locators: List[Tuple[By, str]]):
        for loc in locators:
            try:
                self.click(loc)
                return
            except TimeoutException:
                continue
        raise TimeoutException("BillingStep continue button not found")


class DeliveryStep(CheckoutStep):
    CONTINUE = (By.ID, "button-shipping-address")

    def perform(self):
        try:
            self.click(self.CONTINUE)
        except TimeoutException:
            # If the demo uses a single-page simple checkout, this step may not be present; ignore.
            pass


class ShippingMethodStep(CheckoutStep):
    CONTINUE = (By.ID, "button-shipping-method")

    def perform(self):
        try:
            self.click(self.CONTINUE)
        except TimeoutException:
            pass


class PaymentStep(CheckoutStep):
    TERMS = (By.NAME, "agree")
    CONTINUE = (By.ID, "button-payment-method")

    def perform(self):
        # Terms may be required
        try:
            if self.exists(self.TERMS, quick=False):
                self.click(self.TERMS)
        except Exception:
            pass
        try:
            self.click(self.CONTINUE)
        except TimeoutException:
            pass


class ConfirmStep(CheckoutStep):
    CONFIRM = (By.ID, "button-confirm")

    def perform(self):
        self.click(self.CONFIRM)


# ------------- Test Data -------------
fake = Faker()

@dataclass
class User:
    first: str
    last: str
    email: str
    phone: str
    password: str

def new_user() -> User:
    ts = int(time.time())
    return User(
        first=fake.first_name(),
        last=fake.last_name(),
        email=f"tester{ts}@example.com",
        phone="03001234567",
        password="P@ssw0rd!"
    )


# ------------- Driver bootstrap -------------
def make_driver():
    opts = Options()
    opts.add_argument("--start-maximized")
    # opts.add_argument("--headless=new")  # uncomment for headless/CI
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.implicitly_wait(5)
    return driver


# ------------- End-to-end flow -------------
def run_e2e():
    driver = make_driver()
    try:
        home = HomePage(driver)
        home.open(BASE_URL)

        # SIGNUP
        home.go_register()
        user = new_user()
        RegisterPage(driver).register(
            user.first, user.last, user.email, user.phone, user.password
        )

        # DASHBOARD verify
        dash = AccountDashboardPage(driver)
        assert dash.is_loaded(), "Account dashboard not loaded after registration"

        # LOGOUT & LOGIN
        dash.logout()
        home.go_login()
        LoginPage(driver).login(user.email, user.password)
        assert dash.is_loaded(), "Dashboard not loaded after login"

        # PRODUCT SEARCH + ADD
        home.search("MacBook")
        product = ProductPage(driver)
        product.open_first_result()
        product.add_to_cart()

        # VIEW CART
        cart = CartPage(driver)
        cart.open_cart()

        # CHECKOUT
        cart.proceed_to_checkout()

        # Polymorphic step execution: each has .perform()
        steps: List[CheckoutStep] = [
            BillingStep(driver),
            DeliveryStep(driver),
            ShippingMethodStep(driver),
            PaymentStep(driver),
            ConfirmStep(driver),
        ]
        for s in steps:
            try:
                s.perform()
            except TimeoutException:
                # some steps may be skipped depending on demo configuration
                pass

        # ASSERT SUCCESS
        success = CheckoutPage(driver).success_message()
        print("Checkout success header:", success)
        assert ("Your order has been placed" in success) or ("Success" in success), \
            f"Unexpected success text: {success}"

        print("\nE2E PASSED ✅")
        print(f"Registered user: {user.email} / {user.password}")

    finally:
        # Keep window a moment to view the result (optional)
        time.sleep(2)
        driver.quit()


if __name__ == "__main__":
    run_e2e()
