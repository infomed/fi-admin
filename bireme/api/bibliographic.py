# coding: utf-8
from django.conf import settings
from django.conf.urls import patterns, url, include

from django.contrib.contenttypes.models import ContentType

from tastypie.serializers import Serializer
from tastypie.utils import trailing_slash
from tastypie import fields

from biblioref.models import Reference
from isis_serializer import ISISSerializer

from tastypie_custom import CustomResource

from main.models import Descriptor, ResourceThematic
from biblioref.field_definitions import field_tag_map

import requests
import urllib
import json


class ReferenceResource(CustomResource):

    class Meta:
        queryset = Reference.objects.filter(status=1)
        allowed_methods = ['get']
        serializer = ISISSerializer(formats=['json', 'xml', 'isis_id'], field_tag=field_tag_map)
        resource_name = 'bibliographic'
        filtering = {
            'update_date': ('gte', 'lte'),
            'status': 'exact',
        }
        include_resource_uri = True

    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/search%s$" % (self._meta.resource_name, trailing_slash()),
                self.wrap_view('get_search'), name="api_get_search"),
        ]

    def get_search(self, request, **kwargs):
        self.method_check(request, allowed=['get'])
        self.is_authenticated(request)
        self.throttle_check(request)

        q = request.GET.get('q', '')
        fq = request.GET.get('fq', '')
        start = request.GET.get('start', '')
        count = request.GET.get('count', '')
        lang = request.GET.get('lang', 'pt')
        op = request.GET.get('op', 'search')
        id = request.GET.get('id', '')
        sort = request.GET.get('sort', 'created_date desc')

        # filter result by approved resources (status=1)
        if fq != '':
            fq = '(status:1 AND django_ct:biblioref.reference*) AND %s' % fq
        else:
            fq = '(status:1 AND django_ct:biblioref.reference*)'

        # url
        search_url = "%siahx-controller/" % settings.SEARCH_SERVICE_URL

        search_params = {'site': 'fi', 'col': 'main', 'op': op, 'output': 'site', 'lang': lang,
                         'q': q, 'fq': fq, 'start': start, 'count': count, 'id': id, 'sort': sort}

        r = requests.post(search_url, data=search_params)

        self.log_throttled_access(request)
        return self.create_response(request, r.json())

    def dehydrate(self, bundle):
        # retrive child class of reference (analytic or source) for use in ContentType query
        child_class = bundle.obj.child_class()
        c_type = ContentType.objects.get_for_model(child_class)

        descriptors = Descriptor.objects.filter(object_id=bundle.obj.id, content_type=c_type, status=1)
        thematic_areas = ResourceThematic.objects.filter(object_id=bundle.obj.id, content_type=c_type, status=1)

        # add fields to output
        bundle.data['MFN'] = bundle.obj.id
        bundle.data['descriptors'] = [{'text': descriptor.code} for descriptor in descriptors]
        bundle.data['thematic_areas'] = [{'text': thematic.thematic_area.name} for thematic in thematic_areas]

        return bundle