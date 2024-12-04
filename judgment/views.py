from django.shortcuts import render

from . import forms, models
from django.views.generic.edit import CreateView
from django.views.generic import ListView, DetailView, TemplateView
from django.urls import reverse_lazy
from django.http import JsonResponse, Http404
from django.core.exceptions import PermissionDenied

import json
import logging

logger = logging.getLogger(__name__)

class EventAddView(CreateView):
    template_name = "judgment/add_event.html"
    form_class = forms.EventAddForm
    success_url = reverse_lazy('judgment:event_added')

    def form_valid(self, form):
        return super().form_valid(form)

class EventListView(ListView):
    template_name = "judgment/event_list.html"
    def get(self, request, *args, **kwargs):
        param = None
        desc = ""
        if 'p' in self.request.GET:
            param = self.request.GET['p']
        if param == 'reserved':
            self.object_list = models.Event.get_consolidated_cases(reserved=True)
            desc = "reserved"
        elif param == '3m':
            self.object_list = models.Event.get_consolidated_cases(reserved=True, months=3)
            desc = "reserved at least three months ago"
        elif param == '6m':
            self.object_list = models.Event.get_consolidated_cases(reserved=True, months=6)
            desc = "reserved at least six months ago"
        else:
            self.object_list = models.Event.get_consolidated_cases()
        context = self.get_context_data(object_list=self.object_list)
        context["desc"] = desc
        return self.render_to_response(context)


class EventAddedView(TemplateView):
    template_name = "judgment/event_added.html"


def get_case(request):
    case_id = None
    try:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            try:
                post_data = json.loads(request.body.decode("utf-8"))
                case_id = post_data['case_id'].replace(" ", "")
                cases = models.Event.get_consolidated_cases([case_id,])
                if cases:
                    data = cases[0]
                else:
                    data = {'case_id': ''}
            except Exception as e:
                logger.error("Can't fetch case_id %s: %s" %
                        (case_id, str(e)))
                raise Http404
            return JsonResponse(data)
        else:
            logger.error("get_case must be called as JSON")
            raise PermissionDenied()
    except PermissionDenied:
        raise
    except Exception as e:
        logger.error("Something went wrong: %s" % (case_id, str(e)))
        raise Http404
