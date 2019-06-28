import base64
from collab import models
from collab.choices import STATUS
from collab.db_utils import commit_data

from collab.views.services.feature_services import get_feature
from collab.views.services.feature_services import get_feature_structure

from collab.views.services.project_services import project_feature_type_fields
from collab.views.services.user_services import authenticate_user

import datetime
from django.contrib.gis.geos import GEOSGeometry
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
import json
import uuid
APP_NAME = __package__.split('.')[0]


@csrf_exempt
def export_data(request):
    """
        Export list of feature
    """
    project_slug = 'test'
    feature_type_slug = 'test123'
    list_uuid = ['afd028a0-db2a-4b0b-a913-ef59f44f05ca']
    res = []
    if request.POST.get('project_slug', '') and request.POST.get('feature_type_slug', ''):
        for feature_id in list_uuid:
            feature = get_feature(APP_NAME, project_slug, feature_type_slug, feature_id)
            # export only the features which have been published
            if int(feature.get('status', '')) > 1:
                feature['geom'] = json.loads(feature.get('geom', ''))
                feature['status'] = STATUS[int(feature['status'])][1]
                user = models.CustomUser.objects.get(id=feature.get('user_id', ''))
                if user:
                    feature['user'] = user.username
                feature['link'] = """{domain}projet/{project_slug}/{feature_type}/{feature_id}""".format(
                                  domain=request.build_absolute_uri('/'),
                                  project_slug=project_slug,
                                  feature_type=feature_type_slug,
                                  feature_id=feature_id)
                res.append(feature)
        return JsonResponse(res, safe=False)
    else:
        return JsonResponse({'erreur': 'le project slug et/ou le feature slug sont manquants'},
                            status=400, safe=False)


def get_json_feature_model(request):
    """
        Get json structure for the import
    """
    res = []
    json_structure = []
    if request.GET.get('project_slug', '') and request.GET.get('feature_type_slug', ''):
        project_slug = request.GET.get('project_slug', '')
        feature_type_slug = request.GET.get('feature_type_slug', '')
        project = get_object_or_404(models.Project, slug=project_slug)
        # Basic structure
        basic_res = project_feature_type_fields(APP_NAME, project_slug,
                                                feature_type_slug)
        basic_res.pop('feature_id', None)
        basic_res.pop('project_id', None)
        basic_res.pop('user_id', None)
        basic_res.pop('modification_date', None)
        basic_res.pop('creation_date', None)
        for key, val in basic_res.items():
            if key == 'geom':
                basic_res[key] = project.get_geom(feature_type_slug) + " format WKT"
            elif key == 'status':
                basic_res[key] = ','.join(dict(STATUS).keys()).replace(',',' ou ')
            else:
                basic_res[key] = str(basic_res[key]['type']) + " / " + str(basic_res[key]['data_type'])
        json_structure.append(basic_res)
        json_structure.append(basic_res)
        # get an example of data
        res = get_feature_structure(APP_NAME, project_slug, feature_type_slug)
        for elt in res:
            elt.pop('feature_id', None)
            elt.pop('project_id', None)
            elt.pop('user_id', None)
            elt.pop('modification_date', None)
            elt.pop('creation_date', None)
            for key, val in elt.items():
                if key == 'status':
                    elt[key] = ','.join(dict(STATUS).keys()).replace(',', ' ou ')
        json_structure = json_structure + res
        return JsonResponse(json_structure, safe=False)
    else:
        return JsonResponse({'erreur': 'le project slug et/ou le feature slug sont manquants'},
                            status=400, safe=False)


@csrf_exempt
def import_data(request):
    """
        Import list of feature in json into the database
    """
    project_slug = 'test'
    feature_type_slug = 'testexport'
    # authentification
    user = ""
    if 'HTTP_AUTHORIZATION' in request.META:
        auth = request.META['HTTP_AUTHORIZATION'].split()
        user = authenticate_user(auth)

    if user is None or not user:
        return JsonResponse({'erreur': "Vous n'êtes pas autorisé à acceder à cette page"},
                             status=401, safe=False)
    if request.body:
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception as e:
            return JsonResponse({'erreur': "Les données fournies ne sont pas au format JSON"},
                                status=400, safe=False)
        # data = [{
        #             "archive_date": "2015-10-10",
        #             "status": "1",
        #             "geom": "POLYGON((101.23 171.82, 201.32 101.5, 215.7 201.953, 101.23 171.82))",
        #             "title": "coco",
        #             "text": "lefjed'un'point''lfjlelkfjelf",
        #             "pointentier": "12",
        #             "bool2": "False",
        #             "pointentier2": "12",
        #             "stringa": "ddddddd",
        #             "description": "dddddd",
        #             "reeel1": "10.5",
        #             "bool1": "False",
        #             "deletion_date": "2015-10-10",
        #             "date1": "2019-06-27 12:41:51.897562+02"
        #         },{
        #             "archive_date": "2020-10-10",
        #             "status": "2",
        #             "geom": "POLYGON((101.23 171.82, 201.32 101.5, 215.7 201.953, 101.23 171.82))",
        #             "title": "coco3",
        #             "text": "dedemfkmelfkeml",
        #             "pointentier": "10",
        #             "bool2": "True",
        #             "pointentier2": "12",
        #             "stringa": "fekkek",
        #             "description": "dmd ' 'v'''''mdmdmdmmdt",
        #             "reeel1": "10.5",
        #             "bool1": "False",
        #             "deletion_date": "2019-10-10",
        #             "date1": "2019-06-27 12:41:51.897562+02"
        #         }]
        # format les données ajout des clé
        project = get_object_or_404(models.Project,
                                    slug=project_slug)
        table_name = """{app_name}_{project_slug}_{feature_type_slug}""".format(
                     app_name=APP_NAME,
                     project_slug=project_slug,
                     feature_type_slug=feature_type_slug)
        for elt in data:

            # add srid
            if elt.get('geom', ''):
                try:
                    elt['geom'] = str(GEOSGeometry(elt['geom'], srid=settings.DB_SRID))
                except Exception as e:
                    pass
            # clé auto généré
            elt['project_id'] = str(project.id)
            elt['user_id'] = str(user.id)
            elt['creation_date'] = str(datetime.datetime.now())
            elt['modification_date'] = str(datetime.datetime.now())
            elt['feature_id'] = str(uuid.uuid4())
        res = []
        if request.POST.get('project_slug', project_slug) and request.POST.get('feature_type_slug', feature_type_slug):
            creation = ""
            for feature in data:
                # escape simple quote
                for key, val in feature.items():
                    if "'" in val:
                        feature[key] = val.replace("'", "''")
                try:
                    sql = """INSERT INTO "{table_name}" SELECT *
                             FROM json_populate_record(NULL::"{table_name}", '{feature}');""".format(
                                table_name=table_name,
                                feature=json.dumps(feature)
                             )
                    creation = commit_data('default', sql)
                    if creation == True:
                        res.append("insertion")
                    else:
                        res.append("erreur " + str(creation))
                except Exception as e:
                    res.append("erreur " + str(creation))
            return JsonResponse(res, safe=False)
        else:
            return JsonResponse({'erreur': 'le project slug et/ou le feature slug sont manquants'},
                                status=400, safe=False)
    else:
        return JsonResponse({'erreur': "Aucune donné n'est fourni"},
                            status=400, safe=False)
