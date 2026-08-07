import datetime
from decimal import *

from bs4 import BeautifulSoup as bs
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from letters.models import Letter
from newsroom import utils
from newsroom.models import (
    Article,
    Category,
    Topic,
    Author,
    Correction,
    MostPopular,
    MostDeeplyRead,
)
from republisher.models import Republisher, RepublisherArticle
import republisher.management.commands.emailrepublishers as emailrepublishers
import newsroom.management.commands.notifycorrections as notifycorrections
from pgsearch.utils import searchArticlesAndPhotos
from django.contrib.sites.models import Site
from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from django.contrib.flatpages.models import FlatPage
from django.urls import reverse


class HtmlCleanUp(TestCase):
    def test_html_cleaners(self):
        """HTML is correctly cleaned"""

        html = "<p class='plod'></p><p>Hello</p><p class=''> &nbsp; </p><p class='test'> Good bye </p>"
        self.assertEqual(
            utils.remove_unnecessary_white_space(html),
            "<p>Hello</p><p class='test'> Good bye </p>",
        )

        html = bs(
            '<p><img alt="" src="/media/uploads/church-SiyavuyaKhaya-20150128.jpg" style="width: 1382px; height: 1037px;" /></p><p class="caption">This is the caption.</p>',
            "html.parser",
        )
        self.assertEqual(
            str(utils.replaceImgHeightWidthWithClass(html)),
            '<p><img alt="" src="/media/uploads/church-SiyavuyaKhaya-20150128.jpg"/></p><p class="caption">This is the caption.</p>',
            "html.parser",
        )

        html = bs(
            '<p><img alt="" src="/media/uploads/church-SiyavuyaKhaya-20150128.jpg" style="width: 1382px; height: 1037px;" /></p><p class="caption">This is the caption.</p>',
            "html.parser",
        )
        # self.assertEqual(str(utils.replacePImgWithFigureImg(html)),
        #                 '<figure><img alt="" src="/media/uploads/church-SiyavuyaKhaya-20150128.jpg" style="width: 1382px; height: 1037px;"/><figcaption>This is the caption.</figcaption></figure>')
        html = '<p><img alt="" src="/media/uploads/church-SiyavuyaKhaya-20150128.jpg" style="width: 1382px; height: 1037px;" /></p><p class="caption">This is the caption.</p>'
        self.assertEqual(
            utils.replaceBadHtmlWithGood(html),
            '<p><img alt="" src="/media/uploads/church-SiyavuyaKhaya-20150128.jpg"/></p><p class="caption">This is the caption.</p>',
        )
        html1 = (
            "<p>The dog ran away.</p>"
            "<p>The dog -- ran away.</p>"
            "<p>The dog --- ran away.</p>"
            "<p>The dog--ran away.</p>"
            "<p>The dog---ran away.</p>"
        )
        html2 = (
            "<p>The dog ran away.</p>"
            "<p>The dog – ran away.</p>"
            "<p>The dog — ran away.</p>"
            "<p>The dog--ran away.</p>"
            "<p>The dog---ran away.</p>"
        )
        html3 = str(utils.processDashes(bs(html1, "html.parser")))
        self.assertEqual(html2, html3)


class ArticleTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()

        topic = Topic()
        topic.name = "government"
        topic.slug = "government"
        topic.save()

        category = Category()
        category.name = "Feature"
        category.slug = "feature"
        category.save()

        category = Category()
        category.name = "Photo essay"
        category.slug = "photo-essay"
        category.save()

        category = Category()
        category.name = "Opinion"
        category.slug = "opinion"
        category.save()

        category = Category()
        category.name = "Photo"
        category.slug = "photo"
        category.save()

        category = Category()
        category.name = "News"
        category.slug = "news"
        category.save()

        a = Article()
        a.title = "Test article 1"
        a.body = "<p>The quick brown fox jumps over the lazy dog.</p>"
        a.slug = "test-article-1"
        a.category = Category.objects.get(name="News")
        a.external_primary_image = "http://www.w3schools.com/html/pic_mountain.jpg"
        a.save()
        a.publish_now()

        a = Article()
        a.title = "Test article 2"
        a.subtitle = "Dogs and things"
        a.body = "<p>How now brown cow.</p>"
        a.slug = "test-article-2"
        a.category = Category.objects.get(slug="opinion")
        a.save()
        a.publish_now()

        author = Author()
        author.first_names = "Joe"
        author.last_name = "Bloggs"
        author.email = "joebloggs@example.com"
        author.save()
        a.author_01 = author
        a.save()

    def test_articles(self):
        articles = Article.objects.all()
        self.assertEqual(len(articles), 2)
        articles = Article.objects.published()
        self.assertEqual(len(articles), 2)
        article = Article.objects.published()[1]
        self.assertEqual(article.title, "Test article 1")
        self.assertEqual(
            article.cached_primary_image,
            "http://www.w3schools.com/html/pic_mountain.jpg",
        )
        article = Article.objects.published()[0]
        self.assertEqual(article.title, "Test article 2")

    def test_pages(self):
        client = Client()
        response = client.get("/article/test-article-1/")
        self.assertEqual(response.status_code, 200)
        client = Client()
        response = client.get("/article/test-article-2/")
        self.assertEqual(response.status_code, 200)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        response = client.get("/article/no-exist/")
        self.assertEqual(response.status_code, 404)
        response = client.get("/content/test-article-1/")
        self.assertEqual(response.status_code, 302)
        response = client.get("/category/")
        self.assertEqual(response.status_code, 200)
        response = client.get("/category/News/")
        self.assertEqual(response.status_code, 200)
        response = client.get("/category/news/")
        self.assertEqual(response.status_code, 200)
        response = client.get("/category/Opinion/")
        self.assertEqual(response.status_code, 200)
        response = client.get("/category/opinion/")
        self.assertEqual(response.status_code, 200)
        response = client.get("/topic/")
        self.assertEqual(response.status_code, 200)
        topic = Topic.objects.all()[0]
        url = reverse(
            "newsroom:topic.detail",
            args=[
                topic,
            ],
        )
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        response = client.get("/author/")
        self.assertEqual(response.status_code, 200)
        author = Author.objects.all()[0]
        url = "/author/" + str(author.pk) + "/"
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        url = reverse("newsroom:author.add")
        response = client.get(url)
        url = reverse("newsroom:topic_create")
        response = client.get(url)
        self.assertEqual(response.status_code, 302)
        reponse = client.get(url)
        self.assertEqual(response.status_code, 302)

        user = User.objects.create_user("staff", "staff@example.com", "abcde")
        user.is_staff = True
        user.is_active = True
        permission1 = Permission.objects.get(name="Can add author")
        user.user_permissions.add(permission1)
        permission2 = Permission.objects.get(name="Can change author")
        user.user_permissions.add(permission2)
        permission3 = Permission.objects.get(name="Can add topic")
        user.user_permissions.add(permission3)
        permission4 = Permission.objects.get(name="Can change topic")
        user.user_permissions.add(permission4)
        user.save()

        staff = Client()
        staff.login(username="staff", password="abcde")
        url = reverse(
            "newsroom:author.update",
            args=[
                author.pk,
            ],
        )
        response = staff.get(url)
        self.assertEqual(response.status_code, 200)

        response = staff.get(url)
        self.assertEqual(response.status_code, 200)
        url = reverse(
            "newsroom:topic_update",
            args=[
                topic.pk,
            ],
        )
        response = staff.get(url)
        self.assertEqual(response.status_code, 200)

    def test_duplicate_save(self):
        a = Article()
        a.title = "Test article 3"
        a.category = Category.objects.get(name__iexact="news")
        a.slug = "test-article-1"
        shouldHaveFailed = True
        try:
            a.save()
        except IntegrityError:
            shouldHaveFailed = False
        self.assertEqual(shouldHaveFailed, False)

    def test_published(self):
        num_published = Article.objects.published().count()
        a = Article()
        a.title = "Test article 3"
        a.slug = "test-article-3"
        a.category = Category.objects.get(name="News")
        a.published = timezone.now()
        a.save()
        num_published_now = Article.objects.published().count()
        self.assertEqual(num_published + 1, num_published_now)
        a = Article()
        a.title = "Test article 4"
        a.category = Category.objects.get(name="News")
        a.slug = "test-article-4"
        a.published = timezone.now() + datetime.timedelta(hours=10)
        a.save()
        num_published_now = Article.objects.published().count()
        self.assertEqual(num_published + 1, num_published_now)
        self.assertEqual(a.is_published(), False)

    def test_serialize(self):
        num_published = Article.objects.published().count()
        self.assertTrue(num_published > 0)
        from django.core import serializers

        data = serializers.serialize("xml", Article.objects.published())
        objs = serializers.deserialize("xml", data)
        self.assertTrue(len(list(objs)) == num_published)

    def test_letter(self):
        letter = Letter()
        article = Article.objects.published()[0]
        letter.article = article
        letter.byline = "John Doe"
        letter.email = "johndoe@example.com"
        letter.title = "Test"
        letter.text = "Dear sir. This is a test"
        letter.rejected = False
        letter.published = timezone.now()
        letter.save()
        count = Letter.objects.published().count()
        self.assertEqual(count, 1)
        letter = Letter.objects.published()[0]

        c = Client()
        url = reverse("letters:letter_thanks")
        response = c.get(url)
        self.assertEqual(response.status_code, 200)
        url = reverse("letters:letter_to_editor", args=(article.pk,))
        response = c.get(url)
        self.assertEqual(response.status_code, 200)

        letter = Letter()
        article = Article.objects.published()[0]
        letter.article = article
        letter.byline = "Jane Smith"
        letter.email = "janedoe@this_is_an_invalid_domain.com"
        letter.title = "Test"
        letter.text = "Dear Madam. This is a test"
        letter.rejected = True
        letter.save()

        from letters.management.commands import processletters

        processletters.process()
        letters = Letter.objects.all()
        for l in letters:
            self.assertEqual(l.notified_letter_writer, True)

    def test_preview(self):
        article = Article.objects.get(slug="test-article-1")
        client = Client()
        response = client.get("/prev_gen/" + str(article.pk))
        self.assertEqual(response.status_code, 302)
        response = client.get("/prev_gen/test-article-1/")
        self.assertEqual(response.status_code, 404)
        article = Article.objects.get(slug="test-article-1")
        self.assertTrue(len(article.secret_link) > 40)
        user = User.objects.create_user("admin", "admin@example.com", "abcde")
        user.is_staff = True
        user.is_active = True
        permission = Permission.objects.get(name="Can change article")
        user.user_permissions.add(permission)
        user.save()
        client.login(username="admin", password="abcde")
        response = client.get("/prev_gen/" + str(article.pk))
        self.assertEqual(response.status_code, 302)
        article = Article.objects.get(slug="test-article-1")
        self.assertTrue(len(article.secret_link) > 0)
        response = client.get("/preview/" + article.secret_link + "/")
        self.assertEqual(response.status_code, 302)
        article.published = None
        article.save()
        response = client.get("/preview/" + article.secret_link + "/")
        self.assertEqual(response.status_code, 200)

    def test_search(self):
        articles = searchArticlesAndPhotos("cow dog")
        self.assertEqual(len(articles), 1)

    def test_corrections(self):
        article = Article.objects.get(slug="test-article-1")
        client = Client()
        response = client.get(reverse("newsroom:correction.list"))
        self.assertEqual(response.status_code, 200)
        user = User.objects.create_user("admin", "admin@example.com", "abcde")
        user.is_staff = True
        user.is_active = True
        permission = Permission.objects.get(name="Can add correction")
        user.user_permissions.add(permission)
        permission = Permission.objects.get(name="Can change correction")
        user.user_permissions.add(permission)
        permission = Permission.objects.get(name="Can delete correction")
        user.user_permissions.add(permission)
        user.save()
        client.login(username="admin", password="abcde")
        response = client.get(
            reverse("newsroom:correction.create") + "?article_pk=" + str(article.pk)
        )
        self.assertEqual(response.status_code, 200)
        correction = Correction()
        correction.article = article
        correction.update_type = "C"
        correction.text = "This is a test of the corrections."
        correction.save()
        correction = Correction.objects.get(pk=correction.pk)
        response = client.get(
            reverse("newsroom:correction.update", args=[correction.pk])
            + "?article_pk="
            + str(correction.article.pk)
        )
        self.assertEqual(response.status_code, 200)
        response = client.get(
            reverse("newsroom:correction.delete", args=[correction.pk])
            + "?article_pk="
            + str(correction.article.pk)
        )
        self.assertEqual(response.status_code, 200)
        response = client.get(reverse("newsroom:article.add"))
        self.assertEqual(response.status_code, 200)

        client = Client()
        response = client.get(reverse("newsroom:correction.update", args=[1]))
        self.assertEqual(response.status_code, 302)
        response = client.get(reverse("newsroom:correction.delete", args=[1]))
        self.assertEqual(response.status_code, 302)
        response = client.get(
            reverse("newsroom:correction.create") + "?article_pk=" + str(article.pk)
        )
        self.assertEqual(response.status_code, 302)
        response = client.get(reverse("newsroom:article.add"))
        self.assertEqual(response.status_code, 302)

    def test_flatpages(self):
        f = FlatPage()
        f.url = "/about/"
        f.title = "About page"
        f.content = "<p>About</p>"
        f.save()
        s = Site.objects.all()[0]
        f.sites.add(s)
        f.save()
        client = Client()
        response = client.get("/about/")
        self.assertEqual(response.status_code, 200)

    def add_corrections(self, articles):
        j = 0
        for a in articles:
            if j % 2 == 0:
                notify_republishers = True
            else:
                notify_republishers = False
            j = j + 1
            for i in range(2):
                if i == 1:
                    update_type = "C"
                else:
                    update_type = "U"
                Correction.objects.create(
                    article=a,
                    update_type=update_type,
                    text="We corrected the spelling of John Bloggs",
                    notify_republishers=notify_republishers,
                )

    def test_correction_republisher_notification(self):
        for i in range(5):
            Republisher.objects.create(
                name="Name" + str(i),
                email_addresses="email"
                + str(i)
                + "a@example.com,"
                + "email"
                + str(i)
                + "b@example.com",
                message="Dear republisher " + str(i),
                slug="republisher" + str(i),
            )
        republishers = Republisher.objects.all()
        articles = Article.objects.published()
        for a in articles:
            for r in republishers:
                republisher_article = RepublisherArticle.objects.create(
                    article=a, republisher=r
                )
        res = emailrepublishers.process()
        self.assertEqual(res["failures"], 0)
        self.assertEqual(res["successes"], len(articles) * len(republishers))
        # We add a bunch of corrections, process them twice. Then repeat.
        self.add_corrections(articles)
        res = notifycorrections.process(1)
        self.assertEqual(res["failures"], 0)
        self.assertEqual(res["successes"], 10)
        # Repeat with nothing happening
        res = notifycorrections.process(1)
        self.assertEqual(res["failures"], 0)
        self.assertEqual(res["successes"], 0)
        # And repeat from the top
        self.add_corrections(articles)
        res = notifycorrections.process(1)
        self.assertEqual(res["failures"], 0)
        self.assertEqual(res["successes"], 10)
        # Repeat with nothing happening
        res = notifycorrections.process(1)
        self.assertEqual(res["failures"], 0)
        self.assertEqual(res["successes"], 0)


class ArticleDetailTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.topic = Topic.objects.create(name="Test Topic", slug="test-topic")
        cls.category = Category.objects.create(
            name="Test Category", slug="test-category"
        )
        cls.author = Author.objects.create(
            first_names="Test", last_name="Author", email="test@example.com"
        )
        cls.article = Article.objects.create(
            title="Test Article", slug="test-article", category=cls.category
        )
        cls.article.author_01 = cls.author
        cls.article.topics.add(cls.topic)
        cls.article.save()

    def test_article_absolute_url(self):
        self.assertEqual(
            self.article.get_absolute_url(), f"/article/{self.article.slug}/"
        )

    def test_article_str(self):
        self.assertEqual(str(self.article), f"{self.article.pk} {self.article.title}")

    def test_unpublished_article_not_visible(self):
        c = Client()
        response = c.get(self.article.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_published_article_visible(self):
        self.article.publish_now()
        c = Client()
        response = c.get(self.article.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.article.title)

    def test_article_authors(self):
        self.assertEqual(self.article.author_01, self.author)
        self.assertEqual(self.article.author_02, None)

    def test_article_topics(self):
        self.assertIn(self.topic, self.article.topics.all())


class CategoryTest(TestCase):
    def test_category_creation(self):
        category = Category.objects.create(name="Test Category", slug="test-category")
        self.assertEqual(str(category), category.name)
        self.assertEqual(category.get_absolute_url(), f"/category/{category.slug}/")


####################################################################
# JSON API tests: /api/most-popular/ and /api/most-deeply-read/
#
# Add these imports to the top of newsroom/tests.py if not present:
#
#   from django.test import Client, TestCase, override_settings
#   from newsroom.models import MostPopular, MostDeeplyRead
#   import datetime
#   from django.urls import reverse
#   from django.utils import timezone
####################################################################


class MostReadApiMixin:
    """Shared tests for the two structurally identical endpoints.

    MostPopular and MostDeeplyRead store the same thing -- newline-separated
    "slug|title" rows in one TextField -- and differ only in the name of the
    accessor. So the API contract is identical and the tests can be too.

    Subclasses supply `model`, `url_name` and `get_list`. Deliberately not a
    TestCase subclass, so the runner doesn't collect it on its own.
    """

    model = None
    url_name = None

    def get_list(self):
        """Call the model's list accessor (named differently on each model)."""
        raise NotImplementedError

    # -- helpers ----------------------------------------------------

    def store(self, article_list):
        """Create a record holding the given raw article_list text."""
        obj = self.model()
        obj.article_list = article_list
        obj.save()
        return obj

    def get_json(self):
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        return response.json()

    def setUp(self):
        self.client = Client()

    # -- accessors behave as the API assumes ------------------------

    def test_accessor_returns_none_when_no_record(self):
        """The model returns None, not [], when the cron has never run."""
        self.assertIsNone(self.get_list())

    def test_accessor_splits_rows_and_fields(self):
        self.store("slug-a|Title A\nslug-b|Title B")
        self.assertEqual(
            self.get_list(),
            [["slug-a", "Title A"], ["slug-b", "Title B"]],
        )

    # -- empty / missing data ---------------------------------------

    def test_no_record_returns_empty_list(self):
        """No MostPopular/MostDeeplyRead row at all -> 200 with an empty list.

        Note this is indistinguishable from a genuinely empty list. See the
        `generated` suggestion in the notes if consumers need to tell them
        apart.
        """
        data = self.get_json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["articles"], [])

    def test_record_with_empty_article_list(self):
        """A saved-but-empty record.

        "".split("\\n") is [""], so the accessor returns [[""]] -- one row of
        one empty string, not []. This is what makes get_most_popular_html()
        fall into its bare `except` (MostPopular only; the MostDeeplyRead
        version guards with len(article) >= 2). The API must filter it.
        """
        self.store("")
        self.assertEqual(self.get_list(), [[""]])
        data = self.get_json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["articles"], [])

    # -- happy path -------------------------------------------------

    def test_returns_stored_articles_in_order(self):
        """Rank order is the stored order and must be preserved."""
        self.store("slug-a|Title A\nslug-b|Title B\nslug-c|Title C")
        data = self.get_json()
        self.assertEqual(data["count"], 3)
        self.assertEqual(
            [a["slug"] for a in data["articles"]],
            ["slug-a", "slug-b", "slug-c"],
        )
        self.assertEqual(
            [a["title"] for a in data["articles"]],
            ["Title A", "Title B", "Title C"],
        )

    def test_urls_are_absolute_and_match_reverse(self):
        self.store("slug-a|Title A")
        article = self.get_json()["articles"][0]
        expected_path = reverse("newsroom:article.detail", args=["slug-a"])
        self.assertEqual(article["url"], "http://testserver" + expected_path)
        self.assertTrue(article["url"].startswith("http://"))

    def test_keys_are_exactly_as_documented(self):
        """Guard against accidentally widening or narrowing the payload."""
        self.store("slug-a|Title A")
        data = self.get_json()
        self.assertEqual(set(data.keys()), {"count", "articles"})
        self.assertEqual(set(data["articles"][0].keys()), {"slug", "title", "url"})

    # -- malformed rows ---------------------------------------------

    def test_trailing_newline_does_not_produce_empty_entry(self):
        """The management commands use "\\n".join, but a stray trailing
        newline (hand-edited via admin, say) yields a final [''] row."""
        self.store("slug-a|Title A\n")
        self.assertEqual(self.get_list(), [["slug-a", "Title A"], [""]])
        data = self.get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["articles"][0]["slug"], "slug-a")

    def test_row_without_pipe_is_skipped(self):
        """A row with no separator has no title; reverse() would still build
        a URL, so it must be dropped explicitly rather than emitted."""
        self.store("slug-a|Title A\nbroken-row-no-pipe\nslug-b|Title B")
        data = self.get_json()
        self.assertEqual(data["count"], 2)
        self.assertEqual([a["slug"] for a in data["articles"]], ["slug-a", "slug-b"])

    def test_blank_slug_is_skipped(self):
        self.store("|Title with no slug\nslug-b|Title B")
        data = self.get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["articles"][0]["slug"], "slug-b")

    def test_blank_title_is_skipped(self):
        self.store("slug-a|\nslug-b|Title B")
        data = self.get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["articles"][0]["slug"], "slug-b")

    def test_pipe_in_title_is_preserved(self):
        """item.split("|") splits on every pipe, so a title containing one
        arrives as 3+ parts. The API rejoins; get_*_html() truncates."""
        self.store("slug-a|Cape Town | Water crisis")
        self.assertEqual(self.get_list(), [["slug-a", "Cape Town ", " Water crisis"]])
        data = self.get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["articles"][0]["title"], "Cape Town | Water crisis")

    def test_whitespace_is_stripped(self):
        self.store("  slug-a  |  Title A  ")
        article = self.get_json()["articles"][0]
        self.assertEqual(article["slug"], "slug-a")
        self.assertEqual(article["title"], "Title A")

    def test_windows_line_endings_are_not_silently_accepted(self):
        r"""Documents current behaviour: the accessor splits on "\n" only, so
        a \r\n-delimited list leaves \r glued to the previous title. The strip()
        in the API removes it. If this ever regresses, titles will end in \r."""
        self.store("slug-a|Title A\r\nslug-b|Title B")
        data = self.get_json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["articles"][0]["title"], "Title A")

    # -- which record is served -------------------------------------

    def test_latest_record_wins(self):
        """Both accessors use .latest("modified"). Every cron run inserts a
        new row rather than updating, so the table grows and only the newest
        row should ever be served."""
        old = self.store("old-slug|Old title")
        new = self.store("new-slug|New title")

        # `modified` is auto_now=True, so save() would overwrite whatever we
        # set. QuerySet.update() bypasses field pre_save and lets us force an
        # unambiguous gap rather than relying on clock resolution.
        self.model.objects.filter(pk=old.pk).update(
            modified=timezone.now() - datetime.timedelta(days=2)
        )
        self.model.objects.filter(pk=new.pk).update(modified=timezone.now())

        data = self.get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["articles"][0]["slug"], "new-slug")

    def test_older_records_are_not_merged_in(self):
        old = self.store("a|A\nb|B\nc|C")
        new = self.store("d|D")
        self.model.objects.filter(pk=old.pk).update(
            modified=timezone.now() - datetime.timedelta(days=2)
        )
        self.assertEqual(self.model.objects.count(), 2)
        self.assertEqual(self.get_json()["count"], 1)

    # -- access control ---------------------------------------------

    def test_anonymous_access_is_allowed(self):
        """The point of the endpoint: no auth, no redirect to a login page."""
        self.store("slug-a|Title A")
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Location", response)

    def test_authenticated_response_is_identical(self):
        """Nothing is user-specific, which is why plain cache_page is safe
        here instead of the site's cache_except_staff wrapper."""
        self.store("slug-a|Title A")
        anonymous = self.get_json()

        User.objects.create_user(
            username="staffer",
            password="pw",
            email="s@example.com",
            is_staff=True,
        )
        self.client.login(username="staffer", password="pw")
        self.assertEqual(self.get_json(), anonymous)

    def test_head_is_allowed(self):
        self.store("slug-a|Title A")
        response = self.client.head(reverse(self.url_name))
        self.assertEqual(response.status_code, 200)

    # -- staleness --------------------------------------------------

    def test_slug_of_deleted_article_is_still_returned(self):
        """Documents a real limitation rather than asserting desired
        behaviour: the stored list is a snapshot of slugs and titles, never
        re-validated against Article. If an article is deleted or unpublished
        after the cron ran, the endpoint keeps advertising it and the URL
        404s. Change this test if you add a published-articles filter.
        """
        self.store("no-such-article|Vanished")
        data = self.get_json()
        self.assertEqual(data["count"], 1)
        detail = self.client.get(data["articles"][0]["url"])
        self.assertEqual(detail.status_code, 404)


# `cache_page` is applied in urls.py, and the project's default cache is a
# FileBasedCache in /var/tmp/django_cache with KEY_PREFIX "gu" -- a real
# directory that persists between test runs. Without this override, a response
# cached by one test is served to the next (and to tomorrow's run), and every
# test above that changes the stored list then re-requests the URL fails
# confusingly. DummyCache makes cache_page a no-op.
DISABLE_CACHE = override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
)


@DISABLE_CACHE
class MostPopularApiTest(MostReadApiMixin, TestCase):
    model = MostPopular
    url_name = "newsroom:api.most_popular"

    def get_list(self):
        return MostPopular.get_most_popular_list()

    def test_endpoint_path(self):
        self.assertEqual(reverse(self.url_name), "/api/most-popular/")


@DISABLE_CACHE
class MostDeeplyReadApiTest(MostReadApiMixin, TestCase):
    model = MostDeeplyRead
    url_name = "newsroom:api.most_deeply_read"

    def get_list(self):
        # Note the shorter, inconsistent accessor name on this model.
        return MostDeeplyRead.get_list()

    def test_endpoint_path(self):
        self.assertEqual(reverse(self.url_name), "/api/most-deeply-read/")


@DISABLE_CACHE
class MostReadApiIntegrationTest(TestCase):
    """One end-to-end check that a URL built by the API actually resolves to a
    live article page, and that the two endpoints stay independent."""

    @classmethod
    def setUpTestData(cls):
        category = Category()
        category.name = "News"
        category.slug = "news"
        category.save()

        article = Article()
        article.title = "Cape Town water crisis deepens"
        article.body = "<p>Test body.</p>"
        article.slug = "cape-town-water-crisis_9999"
        article.category = category
        article.save()
        article.publish_now()
        cls.article = article

    def setUp(self):
        self.client = Client()

    def test_url_resolves_to_the_real_article(self):
        popular = MostPopular()
        popular.article_list = self.article.slug + "|" + self.article.title
        popular.save()

        data = self.client.get(reverse("newsroom:api.most_popular")).json()
        self.assertEqual(data["count"], 1)

        entry = data["articles"][0]
        self.assertEqual(entry["slug"], self.article.slug)
        self.assertEqual(entry["title"], self.article.title)

        detail = self.client.get(entry["url"])
        self.assertEqual(detail.status_code, 200)

    def test_endpoints_read_separate_tables(self):
        popular = MostPopular()
        popular.article_list = "popular-slug|Popular"
        popular.save()

        deeply = MostDeeplyRead()
        deeply.article_list = "deep-slug|Deep"
        deeply.save()

        popular_data = self.client.get(reverse("newsroom:api.most_popular")).json()
        deep_data = self.client.get(reverse("newsroom:api.most_deeply_read")).json()

        self.assertEqual(popular_data["articles"][0]["slug"], "popular-slug")
        self.assertEqual(deep_data["articles"][0]["slug"], "deep-slug")

    def test_populating_one_does_not_populate_the_other(self):
        popular = MostPopular()
        popular.article_list = "popular-slug|Popular"
        popular.save()

        deep_data = self.client.get(reverse("newsroom:api.most_deeply_read")).json()
        self.assertEqual(deep_data["count"], 0)
