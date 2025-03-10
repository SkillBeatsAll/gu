import datetime
from decimal import *

from bs4 import BeautifulSoup as bs
from django.db import IntegrityError
from django.test import Client, TestCase
from django.utils import timezone
from letters.models import Letter
from newsroom import utils
from newsroom.models import Article, Category, Topic, Author, Correction
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
        self.assertEqual(utils.remove_unnecessary_white_space(html),
                         "<p>Hello</p><p class='test'> Good bye </p>")

        html = bs('<p><img alt="" src="/media/uploads/church-SiyavuyaKhaya-20150128.jpg" style="width: 1382px; height: 1037px;" /></p><p class="caption">This is the caption.</p>', "html.parser")
        self.assertEqual(str(utils.replaceImgHeightWidthWithClass(html)),
                         '<p><img alt="" src="/media/uploads/church-SiyavuyaKhaya-20150128.jpg"/></p><p class="caption">This is the caption.</p>', "html.parser")

        html = bs('<p><img alt="" src="/media/uploads/church-SiyavuyaKhaya-20150128.jpg" style="width: 1382px; height: 1037px;" /></p><p class="caption">This is the caption.</p>', "html.parser")
        # self.assertEqual(str(utils.replacePImgWithFigureImg(html)),
        #                 '<figure><img alt="" src="/media/uploads/church-SiyavuyaKhaya-20150128.jpg" style="width: 1382px; height: 1037px;"/><figcaption>This is the caption.</figcaption></figure>')
        html = '<p><img alt="" src="/media/uploads/church-SiyavuyaKhaya-20150128.jpg" style="width: 1382px; height: 1037px;" /></p><p class="caption">This is the caption.</p>'
        self.assertEqual(utils.replaceBadHtmlWithGood(html),
                         '<p><img alt="" src="/media/uploads/church-SiyavuyaKhaya-20150128.jpg"/></p><p class="caption">This is the caption.</p>')
        html1 = "<p>The dog ran away.</p>" \
                "<p>The dog -- ran away.</p>" \
                "<p>The dog --- ran away.</p>" \
                "<p>The dog--ran away.</p>" \
                "<p>The dog---ran away.</p>"
        html2 = "<p>The dog ran away.</p>" \
                "<p>The dog – ran away.</p>" \
                "<p>The dog — ran away.</p>" \
                "<p>The dog--ran away.</p>" \
                "<p>The dog---ran away.</p>"
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
        a.external_primary_image = \
            "http://www.w3schools.com/html/pic_mountain.jpg"
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
        self.assertEqual(article.cached_primary_image,
            "http://www.w3schools.com/html/pic_mountain.jpg")
        article = Article.objects.published()[0]
        self.assertEqual(article.title, "Test article 2")

    def test_pages(self):
        client = Client()
        response = client.get('/article/test-article-1/')
        self.assertEqual(response.status_code, 200)
        client = Client()
        response = client.get('/article/test-article-2/')
        self.assertEqual(response.status_code, 200)
        response = client.get('/')
        self.assertEqual(response.status_code, 200)
        response = client.get('/article/no-exist/')
        self.assertEqual(response.status_code, 404)
        response = client.get('/content/test-article-1/')
        self.assertEqual(response.status_code, 302)
        response = client.get('/category/')
        self.assertEqual(response.status_code, 200)
        response = client.get('/category/News/')
        self.assertEqual(response.status_code, 200)
        response = client.get('/category/news/')
        self.assertEqual(response.status_code, 200)
        response = client.get('/category/Opinion/')
        self.assertEqual(response.status_code, 200)
        response = client.get('/category/opinion/')
        self.assertEqual(response.status_code, 200)
        response = client.get('/topic/')
        self.assertEqual(response.status_code, 200)
        topic = Topic.objects.all()[0]
        url = reverse('newsroom:topic.detail', args=[topic,])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        response = client.get('/author/')
        self.assertEqual(response.status_code, 200)
        author = Author.objects.all()[0]
        url = '/author/' + str(author.pk) + '/'
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        url = reverse('newsroom:author.add');
        response = client.get(url)
        url = reverse('newsroom:topic_create');
        response = client.get(url)
        self.assertEqual(response.status_code, 302)
        reponse = client.get(url);
        self.assertEqual(response.status_code, 302)

        user = User.objects.create_user('staff', 'staff@example.com', 'abcde')
        user.is_staff = True
        user.is_active = True
        permission1 = Permission.objects.get(name='Can add author')
        user.user_permissions.add(permission1)
        permission2 = Permission.objects.get(name='Can change author')
        user.user_permissions.add(permission2)
        permission3 = Permission.objects.get(name='Can add topic')
        user.user_permissions.add(permission3)
        permission4 = Permission.objects.get(name='Can change topic')
        user.user_permissions.add(permission4)
        user.save()

        staff = Client()
        staff.login(username='staff', password='abcde')
        url = reverse('newsroom:author.update', args=[author.pk,])
        response = staff.get(url)
        self.assertEqual(response.status_code, 200)

        response = staff.get(url)
        self.assertEqual(response.status_code, 200)
        url = reverse('newsroom:topic_update', args=[topic.pk,])
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

        c = Client()
        url = reverse('letters:letter_thanks')
        response = c.get(url)
        self.assertEqual(response.status_code, 200)
        url = reverse('letters:letter_to_editor', args=(1,))
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
        response = client.get('/prev_gen/' + str(article.pk))
        self.assertEqual(response.status_code, 302)
        response = client.get('/prev_gen/test-article-1/')
        self.assertEqual(response.status_code, 404)
        article = Article.objects.get(slug="test-article-1")
        self.assertTrue(len(article.secret_link) > 40)
        user = User.objects.create_user('admin', 'admin@example.com', 'abcde')
        user.is_staff = True
        user.is_active = True
        permission = Permission.objects.get(name='Can change article')
        user.user_permissions.add(permission)
        user.save()
        client.login(username='admin', password='abcde')
        response = client.get('/prev_gen/' + str(article.pk))
        self.assertEqual(response.status_code, 302)
        article = Article.objects.get(slug="test-article-1")
        self.assertTrue(len(article.secret_link) > 0)
        response = client.get('/preview/' + article.secret_link + '/')
        self.assertEqual(response.status_code, 302)
        article.published = None
        article.save()
        response = client.get('/preview/' + article.secret_link + '/')
        self.assertEqual(response.status_code, 200)

    def test_search(self):
        articles = searchArticlesAndPhotos("cow dog")
        self.assertEqual(len(articles), 1)

    def test_corrections(self):
        article = Article.objects.get(slug="test-article-1")
        client = Client()
        response = client.get(reverse('newsroom:correction.list'))
        self.assertEqual(response.status_code, 200)
        user = User.objects.create_user('admin', 'admin@example.com', 'abcde')
        user.is_staff = True
        user.is_active = True
        permission = Permission.objects.get(name='Can add correction')
        user.user_permissions.add(permission)
        permission = Permission.objects.get(name='Can change correction')
        user.user_permissions.add(permission)
        permission = Permission.objects.get(name='Can delete correction')
        user.user_permissions.add(permission)
        user.save()
        client.login(username='admin', password='abcde')
        response = client.get(reverse('newsroom:correction.create') +
                                      "?article_pk=" + str(article.pk))
        self.assertEqual(response.status_code, 200)
        correction = Correction()
        correction.article = article
        correction.update_type = "C"
        correction.text = "This is a test of the corrections."
        correction.save()
        correction = Correction.objects.get(pk=correction.pk)
        response = client.get(reverse('newsroom:correction.update', args=[correction.pk]) +
                                      "?article_pk=" + str(correction.article.pk))
        self.assertEqual(response.status_code, 200)
        response = client.get(reverse('newsroom:correction.delete', args=[correction.pk])  +
                                      "?article_pk=" + str(correction.article.pk))
        self.assertEqual(response.status_code, 200)
        response = client.get(reverse('newsroom:article.add'))
        self.assertEqual(response.status_code, 200)

        client = Client()
        response = client.get(reverse('newsroom:correction.update', args=[1]))
        self.assertEqual(response.status_code, 302)
        response = client.get(reverse('newsroom:correction.delete', args=[1]))
        self.assertEqual(response.status_code, 302)
        response = client.get(reverse('newsroom:correction.create') +
                                      "?article_pk=" + str(article.pk))
        self.assertEqual(response.status_code, 302)
        response = client.get(reverse('newsroom:article.add'))
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
        response = client.get('/about/')
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
                    notify_republishers=notify_republishers)

    def test_correction_republisher_notification(self):
        for i in range(5):
            Republisher.objects.create(
                name = "Name" + str(i),
                email_addresses="email" + str(i) + "a@example.com," +
                "email" + str(i) + "b@example.com",
                message="Dear republisher " + str(i),
                slug="republisher" + str(i))
        republishers = Republisher.objects.all()
        articles = Article.objects.published()
        for a in articles:
            for r in republishers:
                republisher_article = RepublisherArticle.objects.create(
                    article=a,
                    republisher=r)
        res = emailrepublishers.process()
        self.assertEqual(res['failures'], 0)
        self.assertEqual(res['successes'], len(articles) * len(republishers))
        # We add a bunch of corrections, process them twice. Then repeat.
        self.add_corrections(articles)
        res = notifycorrections.process(1)
        self.assertEqual(res['failures'], 0)
        self.assertEqual(res['successes'], 10)
        # Repeat with nothing happening
        res = notifycorrections.process(1)
        self.assertEqual(res['failures'], 0)
        self.assertEqual(res['successes'], 0)
        # And repeat from the top
        self.add_corrections(articles)
        res = notifycorrections.process(1)
        self.assertEqual(res['failures'], 0)
        self.assertEqual(res['successes'], 10)
        # Repeat with nothing happening
        res = notifycorrections.process(1)
        self.assertEqual(res['failures'], 0)
        self.assertEqual(res['successes'], 0)

class ArticleDetailTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.topic = Topic.objects.create(name="Test Topic", slug="test-topic")
        cls.category = Category.objects.create(name="Test Category", slug="test-category")
        cls.author = Author.objects.create(
            first_names="Test",
            last_name="Author",
            email="test@example.com"
        )
        cls.article = Article.objects.create(
            title="Test Article",
            slug="test-article",
            category=cls.category
        )
        cls.article.author_01 = cls.author
        cls.article.topics.add(cls.topic)
        cls.article.save()

    def test_article_absolute_url(self):
        self.assertEqual(
            self.article.get_absolute_url(),
            f'/article/{self.article.slug}/'
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
        category = Category.objects.create(
            name="Test Category",
            slug="test-category"
        )
        self.assertEqual(str(category), category.name)
        self.assertEqual(category.get_absolute_url(), 
                        f'/category/{category.slug}/')
