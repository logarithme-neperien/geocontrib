from collab.choices import GEOM_TYPE
from collab.choices import USER_TYPE
from collab.choices import USER_TYPE_ARCHIVE
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import JSONField
from django.contrib.sites.shortcuts import get_current_site
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils.html import format_html
from django.utils.text import slugify
from datetime import timedelta
import os


class CustomUser(AbstractUser):
    # add additional fields in here
    nickname = models.CharField('nickname', max_length=15, blank=True)

    def __str__(self):
        return '%s %s' % (self.first_name, self.last_name.upper())

    def project_right(self, project):
        """
            Return the User project rights
            LEVEL = (
                ('0', 'Utilisateur anonyme'),
                ('1', 'Utilisateur connecté'),
                ('2', 'Contributeur'),
                ('3', 'Modérateur'),
                ('4', 'Administrateur'),
            )
        """
        user_right = {'proj_creation': False,
                      'proj_modification': False,
                      'proj_consultation': False,
                      'feat_archive': False,
                      'feat_creation': False,
                      'feat_modification': False,
                      'feat_consultation': False,
                      'user_admin': False,
                      'model_creation': False}
        # modification if admin or super admin
        try:
            autorisation = Autorisation.objects.get(user=self,
                                                    project=project)
            # Projet
            # if project and feature are visible
            if int(autorisation.level) >= int(project.visi_feature):
                user_right['proj_consultation'] = True
                user_right['feat_consultation'] = True
            if int(autorisation.level) >= 4:
                user_right['proj_modification'] = True
                user_right['user_admin'] = True
            if self.is_superuser:
                user_right['proj_creation'] = True
                user_right['model_creation'] = True
            # Feature
            if int(autorisation.level) >= int(project.visi_archive):
                user_right['feat_archive'] = True
            if int(autorisation.level) >= 3:
                user_right['feat_modification'] = True
            if int(autorisation.level) >= 2:
                user_right['feat_creation'] = True

        except Exception as e:
            # no autorisation
            pass

        return user_right


class Project(models.Model):

    # Admin prepopulated_fields = {"slug": ("titre",)}
    title = models.CharField('Titre', max_length=128, unique=True)
    slug = models.SlugField('Slug', max_length=128, unique=True)
    creation_date = models.DateTimeField("Date de création du projet",
                                          auto_now_add=True)
    description = models.TextField('Description', blank=True)
    illustration = models.ImageField('illustration', upload_to="illustrations", null=True)
    moderation = models.BooleanField('Modération', default=False)
    visi_feature = models.CharField('Visibilité des signalements publiés',
                                    choices=USER_TYPE,
                                    max_length=1, default='0')
    visi_archive = models.CharField('Visibilité des signalements archivés',
                                    choices=USER_TYPE_ARCHIVE,
                                    max_length=1, default='0')
    archive_feature = models.DurationField('Délai avant archivage', blank=True,
                                            null=True)
    delete_feature = models.DurationField('Délai avant suppression',
                                           blank=True, null=True)
    feature_type = JSONField('Type de signalements disponibles',
                             blank=True, null=True)

    def __str__(self):
        return self.title

    def thumbLink(self):
        try:
            return format_html('<img src="{url}" width=200 height=200/>',
                               url=settings.BASE_URL+self.illustration.url)
        except Exception as e:
            pass

    thumbLink.allow_tags = True
    thumbLink.short_description = "Icône"

    def _get_unique_slug(self):
        slug = slugify(self.title)
        unique_slug = slug
        num = 1
        while Project.objects.filter(slug=unique_slug).exists():
            unique_slug = '{}-{}'.format(slug, num)
            num += 1
        return unique_slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._get_unique_slug()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Projet"
        verbose_name_plural = "Projets"

# class Layers(models.Model):
#  TODO
#     name = models.CharField('Nom', max_length=15)
#     project = models.ManyToManyField(Project)
#
#     class Meta:
#         verbose_name = "Couche"
#         verbose_name_plural = "Couches"


class Autorisation(models.Model):
    LEVEL = (
        ('0', 'Utilisateur anonyme'),
        ('1', 'Utilisateur connecté'),
        ('2', "Contribution"),
        ('3', 'Modération'),
        ('4', "Administration"),
    )
    level = models.CharField("Niveau d'autorisation",
                             choices=LEVEL,
                             max_length=1)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    creation_date = models.DateTimeField("Date de création de l'Abonnement",
                                         auto_now_add=True)
    modification_date = models.DateTimeField("Date de modifictaion de l'Abonnement",
                                         auto_now=True)

    class Meta:
        # un role par projet
        unique_together = (
            ('user', 'project'),
        )


class Subscription(models.Model):

    creation_date = models.DateTimeField("Date de création de l'Abonnement",
                                          auto_now_add=True)
    user = models.ForeignKey(CustomUser, verbose_name="Utilisateur",
                             on_delete=models.CASCADE,
                             help_text="Utilisateur abonné")
    feature_id = models.UUIDField("Identifiant du signalement",
                                  editable=False, max_length=32)
    project_slug = models.SlugField('Slug', max_length=128)

    class Meta:
        verbose_name = "Abonnement"
        verbose_name_plural = "Abonnements"


class Comment(models.Model):

    creation_date = models.DateTimeField("Date de création du commentaire",
                                         auto_now_add=True)
    author = models.ForeignKey(CustomUser, verbose_name="Auteur",
                               on_delete=models.PROTECT,
                               help_text="Auteur du commentaire")
    feature_id = models.UUIDField("Identifiant du signalement",
                                  editable=False, max_length=32)
    comment = models.TextField('Commentaire', blank=True)

    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Commentaire"
        verbose_name_plural = "Commentaires"


class Attachment(models.Model):

    OBJET_TYPE = (
        ('0', 'Signalement'),
        ('1', 'Commentaire'),
    )

    title = models.CharField('Titre', max_length=128)

    type_objet = models.CharField("Type d'objet concerné",
                                  choices=OBJET_TYPE,
                                  max_length=1)
    file = models.FileField(
        'Piece jointe',
        upload_to="piecejointe",
        # validators=[] -> TO DO VALIDER L'extension + Taille du fichier
    )

    feature_id = models.UUIDField("Identifiant du signalement",
                                  editable=False, max_length=32, blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True)
    info = models.TextField('Info', blank=True)

    def __str__(self):
        return self.titre

    class Meta:
        verbose_name = "Pièce Jointe"
        verbose_name_plural = "Pièces Jointes"


class Event(models.Model):

    EVEN_TYPE = (
        ('0', 'Création'),
        ('1', "Modification d'une pièce jointe"),
        ('2', 'Modification de la localisation'),
        ('3', "Modification d’un attribut"),
        ('4', 'Suppression'),
        ('5', "Changement de statut"),
    )
    creation_date = models.DateTimeField("Date de l'évènement",
                                         auto_now_add=True)
    user = models.ForeignKey(CustomUser, verbose_name="utilisateur",
                             on_delete=models.CASCADE)
    feature_id = models.UUIDField("Identifiant du signalement",
                                  editable=False, max_length=32)
    object_type = models.CharField("Type d'évènement",
                                   choices=EVEN_TYPE,
                                   max_length=1)
    project_slug = models.SlugField('Slug', max_length=128)
    data = JSONField()

    class Meta:
        verbose_name = "Évènement"
        verbose_name_plural = "Évènements"
