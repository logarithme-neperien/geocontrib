from django.views.generic.base import TemplateView
from django.db.models import Count
from django.db.models import Q
from django.shortcuts import render
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View

from collab.models import Authorization
from collab.models import Project
from collab import choices

DECORATORS = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]


class HomePageView(TemplateView):

    template_name = "collab/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Collab"

        nb_contributors = Count(
            'authorization', filter=Q(authorization__level=choices.CONTRIBUTOR))
        nb_features = Count('feature')
        nb_comments = Count('comment')
        context["projects"] = Project.objects.annotate(
            nb_contributors=nb_contributors,
            nb_features=nb_features,
            nb_comments=nb_comments
        )

        return context


class LoginView(TemplateView):
    """
        Authentification par proxy
    """
    template_name = 'collab/registration/login.html'


class LogoutView(TemplateView):

    template_name = 'collab/registration/login.html'


@method_decorator(DECORATORS, name='dispatch')
class MyAccount(View):

    def get(self, request):
        context = {}
        user = request.user

        context['user'] = user

        nb_contributors = Count(
            'authorization', filter=Q(authorization__level=choices.CONTRIBUTOR))
        nb_features = Count('feature')
        nb_comments = Count('comment')

        # on liste les droits de l'utilisateur pour chaque projet
        context["permissions"] = {}
        for projet in Project.objects.all():
            context["permissions"][projet.slug] = Authorization.has_permission(user, 'can_view_project', projet)

        context["projects"] = Project.objects.annotate(
            nb_contributors=nb_contributors,
            nb_features=nb_features,
            nb_comments=nb_comments,
        )

        return render(request, 'collab/my_account.html', context)


def site_help(request):
    context = {"title": "Aide"}
    return render(request, 'collab/help.html', context)


def legal(request):
    context = {"title": "Mentions légales"}
    return render(request, 'collab/legal.html', context)