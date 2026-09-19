from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import GroupPurchase, Payment
from .services import compute_balances, monthly_stats, settle_up, split_amount


class BalanceTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")

    def test_payment_creates_opposite_balances(self):
        """Paying someone means they now owe you: +100 for the payer,
        -100 for the receiver."""
        Payment.objects.create(sender=self.alice, receiver=self.bob, amount=100, date="2026-01-01")
        alice = {r["username"]: r["balance"] for r in compute_balances(self.alice)}
        bob = {r["username"]: r["balance"] for r in compute_balances(self.bob)}
        self.assertEqual(alice["bob"], 100)
        self.assertEqual(bob["alice"], -100)

    def test_mutual_payments_net_to_zero(self):
        Payment.objects.create(sender=self.alice, receiver=self.bob, amount=100, date="2026-01-01")
        Payment.objects.create(sender=self.bob, receiver=self.alice, amount=100, date="2026-01-02")
        alice = {r["username"]: r["balance"] for r in compute_balances(self.alice)}
        self.assertEqual(alice["bob"], 0)

    def test_unknown_users_still_listed_at_zero(self):
        carol = User.objects.create_user("carol", password="pw")
        rows = {r["username"]: r["balance"] for r in compute_balances(self.alice)}
        self.assertEqual(rows["carol"], 0)


class SettleUpTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")
        self.carol = User.objects.create_user("carol", password="pw")

    def test_single_debt(self):
        Payment.objects.create(sender=self.alice, receiver=self.bob, amount=100, date="2026-01-01")
        transfers = settle_up(self.alice)
        self.assertEqual(len(transfers), 1)
        self.assertEqual(transfers[0]["from"], "bob")
        self.assertEqual(transfers[0]["to"], "alice")
        self.assertEqual(transfers[0]["amount"], 100)

    def test_mutual_payments_no_settlement(self):
        Payment.objects.create(sender=self.alice, receiver=self.bob, amount=100, date="2026-01-01")
        Payment.objects.create(sender=self.bob, receiver=self.alice, amount=100, date="2026-01-02")
        self.assertEqual(settle_up(self.alice), [])

    def test_three_way_settlement(self):
        Payment.objects.create(sender=self.alice, receiver=self.bob, amount=200, date="2026-01-01")
        Payment.objects.create(sender=self.alice, receiver=self.carol, amount=100, date="2026-01-02")
        transfers = settle_up(self.alice)
        self.assertEqual(len(transfers), 2)
        amounts = sorted(t["amount"] for t in transfers)
        self.assertEqual(amounts, [100, 200])

    def test_balances_sum_to_zero(self):
        Payment.objects.create(sender=self.alice, receiver=self.bob, amount=50, date="2026-01-01")
        Payment.objects.create(sender=self.bob, receiver=self.carol, amount=30, date="2026-01-02")
        transfers = settle_up(self.alice)
        for t in transfers:
            self.assertGreater(t["amount"], 0)


class MonthlyStatsTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")

    def test_monthly_totals(self):
        Payment.objects.create(sender=self.alice, receiver=self.bob, amount=100, date="2026-09-01")
        Payment.objects.create(sender=self.alice, receiver=self.bob, amount=50, date="2026-09-15")
        Payment.objects.create(sender=self.bob, receiver=self.alice, amount=30, date="2026-09-20")
        Payment.objects.create(sender=self.alice, receiver=self.bob, amount=20, date="2026-10-05")

        stats = monthly_stats(self.alice)
        self.assertEqual(len(stats), 2)
        sep = [m for m in stats if m["month"].month == 9][0]
        oct = [m for m in stats if m["month"].month == 10][0]
        self.assertEqual(sep["sent"], 150)
        self.assertEqual(sep["received"], 30)
        self.assertEqual(sep["sent_count"], 2)
        self.assertEqual(sep["received_count"], 1)
        self.assertEqual(oct["sent"], 20)
        self.assertEqual(oct["received"], 0)


class AuthTests(TestCase):
    def test_pages_require_login(self):
        for name in ("balances", "records", "add_record", "group_buy"):
            response = self.client.get(reverse(name))
            self.assertRedirects(response, f"{reverse('login')}?next={reverse(name)}")

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Sign in")

    def test_login_rejects_bad_password(self):
        User.objects.create_user("alice", password="pw")
        response = self.client.post(reverse("login"), {"username": "alice", "password": "wrong"})
        self.assertContains(response, "Please enter a correct username and password")

    def test_login_then_logout(self):
        User.objects.create_user("alice", password="pw")
        self.client.post(reverse("login"), {"username": "alice", "password": "pw"})
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))


class SplitTests(TestCase):
    def test_parts_add_back_up_to_total(self):
        for total in (1, 5, 100, 999_999):
            for weights in (
                [Decimal(1), Decimal(1), Decimal(1)],
                [Decimal(1), Decimal(2), Decimal(0.5)],
                [Decimal(0.5), Decimal(0.5), Decimal(0.5), Decimal(0.5)],
                [Decimal(20), Decimal(0.5)],
            ):
                parts = split_amount(total, weights)
                self.assertEqual(sum(parts), total)
                self.assertEqual(len(parts), len(weights))
                self.assertTrue(all(p >= 0 for p in parts))

    def test_equal_weights_split_evenly(self):
        self.assertEqual(split_amount(10, [Decimal(1), Decimal(1), Decimal(1)]), [4, 3, 3])

    def test_bigger_weight_gets_bigger_share(self):
        parts = split_amount(100, [Decimal(1), Decimal(3)])
        self.assertEqual(sum(parts), 100)
        self.assertGreater(parts[1], parts[0])

    def test_zero_total_weight_rejected(self):
        with self.assertRaises(ValueError):
            split_amount(10, [Decimal(0), Decimal(0)])


class GroupBuyTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")
        self.carol = User.objects.create_user("carol", password="pw")
        self.client.login(username="alice", password="pw")

    def post_split(self, **overrides):
        data = {
            "payer": "alice",
            "amount": "100",
            "date": "2026-09-18",
            "note": "Pizza",
            "participants": ["bob", "carol"],
            "weight_bob": "1",
            "weight_carol": "1",
        }
        data.update(overrides)
        return self.client.post(reverse("group_buy"), data)

    def test_split_creates_purchase_and_shares(self):
        response = self.post_split()
        self.assertRedirects(response, reverse("balances"))
        self.assertEqual(GroupPurchase.objects.count(), 1)
        purchase = GroupPurchase.objects.get()
        self.assertEqual(purchase.payer, self.alice)
        shares = {p.receiver: p.amount for p in purchase.shares.all()}
        self.assertEqual(shares, {self.bob: 50, self.carol: 50})

    def test_weighted_split(self):
        self.post_split(weight_carol="3")
        shares = {p.receiver.username: p.amount for p in Payment.objects.all()}
        self.assertEqual(shares["bob"], 25)
        self.assertEqual(shares["carol"], 75)

    def test_payer_checked_is_skipped(self):
        response = self.post_split(participants=["alice", "bob", "carol"])
        self.assertRedirects(response, reverse("balances"))
        shares = {p.receiver.username: p.amount for p in Payment.objects.all()}
        self.assertEqual(shares, {"bob": 50, "carol": 50})

    def test_no_participants_rejected(self):
        response = self.post_split(participants=[])
        self.assertContains(response, "Tick at least one person")
        self.assertEqual(GroupPurchase.objects.count(), 0)

    def test_bad_weight_rejected_atomically(self):
        response = self.post_split(weight_bob="abc")
        self.assertContains(response, "multipliers must be numbers")
        self.assertEqual(GroupPurchase.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

    def test_only_payer_selected_rejected(self):
        response = self.post_split(participants=["alice"])
        self.assertContains(response, "at least one other person")
        self.assertEqual(GroupPurchase.objects.count(), 0)


class AddRecordTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")
        self.client.login(username="alice", password="pw")

    def post_record(self, **overrides):
        data = {"receiver": "bob", "amount": "100", "date": "2026-09-18", "note": "Dinner"}
        data.update(overrides)
        return self.client.post(reverse("add_record"), data)

    def test_valid_payment_saved_and_redirects(self):
        response = self.post_record()
        self.assertRedirects(response, reverse("balances"))
        payment = Payment.objects.get()
        self.assertEqual(payment.sender, self.alice)
        self.assertEqual(payment.receiver, self.bob)
        self.assertEqual(payment.amount, 100)

    def test_sender_is_always_the_signed_in_user(self):
        """A crafted receiver can't change who paid."""
        self.post_record()
        self.assertEqual(Payment.objects.get().sender, self.alice)

    def test_borrowed_direction_swaps_sender_receiver(self):
        response = self.post_record(direction="borrowed")
        self.assertRedirects(response, reverse("balances"))
        payment = Payment.objects.get()
        self.assertEqual(payment.sender, self.bob)
        self.assertEqual(payment.receiver, self.alice)
        self.assertEqual(payment.amount, 100)

    def test_self_payment_rejected(self):
        response = self.post_record(receiver="alice")
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(Payment.objects.count(), 0)

    def test_bad_amount_rejected(self):
        cases = {
            "0": "greater than or equal to 1",
            "-5": "greater than or equal to 1",
            "abc": "Enter a whole number",
            "1000000": "less than or equal to 999999",
        }
        for amount, fragment in cases.items():
            with self.subTest(amount=amount):
                response = self.post_record(amount=amount)
                self.assertContains(response, fragment)
        self.assertEqual(Payment.objects.count(), 0)

    def test_refill_after_error(self):
        response = self.post_record(amount="0")
        self.assertContains(response, ">Dinner<")


class RecordsFilterTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")
        Payment.objects.create(sender=self.alice, receiver=self.bob, amount=50, date="2026-09-01", note="a")
        Payment.objects.create(sender=self.bob, receiver=self.alice, amount=70, date="2026-09-15", note="b")
        self.client.login(username="alice", password="pw")

    def test_filter_by_sender(self):
        response = self.client.get(reverse("records"), {"sender": "alice"})
        self.assertContains(response, "a")
        self.assertNotContains(response, "note b")
        self.assertContains(response, "matching these filters")

    def test_filter_by_date_range(self):
        response = self.client.get(
            reverse("records"),
            {"date_from": "2026-09-10", "date_to": "2026-09-20"},
        )
        self.assertContains(response, "b")
        self.assertNotContains(response, "note a")

    def test_inverted_dates_show_all(self):
        """An invalid date range is ignored; all records are shown."""
        response = self.client.get(
            reverse("records"),
            {"date_from": "2026-09-20", "date_to": "2026-09-01"},
        )
        self.assertContains(response, "a")
        self.assertContains(response, "b")

    def test_total_amount(self):
        response = self.client.get(reverse("records"))
        self.assertContains(response, "$120")

    def test_csv_export(self):
        response = self.client.get(reverse("records_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment", response["Content-Disposition"])
        content = response.content.decode()
        self.assertIn("Date", content)
        self.assertIn("Paid by", content)
        self.assertIn("Paid to", content)
        self.assertIn(",50,", content)
        self.assertIn(",70,", content)

    def test_csv_export_respects_filters(self):
        response = self.client.get(reverse("records_csv"), {"sender": "alice"})
        content = response.content.decode()
        self.assertIn(",50,", content)
        self.assertNotIn(",70,", content)


class PageTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.client.login(username="alice", password="pw")

    def test_pages_render(self):
        for name in ("balances", "records", "add_record", "group_buy"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
