from django.views.generic import ListView, DetailView
from django.http import Http404
from django.contrib import messages
from django.db.models import Q

from newsroom.models import Topic
from pgsearch.utils import searchQandA

from agony.models import QandA

class QandAList(ListView):
    paginate_by = 10

    def get_queryset(self):
        qandas = QandA.objects.published()

        if 'qanda_search_str' in self.request.GET:
            try:
                qandas = searchQandA(self.request.GET.get('qanda_search_str'))
            except:
                pass

        if 'topic' in self.request.GET:
            try:
                topic = int(self.request.GET['topic'])
                qandas = qandas & \
                         QandA.objects.published().filter(topics__in=[topic,])
            except:
                pass

        return qandas


    def get_context_data(self, **kwargs):
        context = super(QandAList, self).get_context_data(**kwargs)
        context['qanda_search'] = True
        
        # query params dict for context -- needed for pagination
        query_params = {}
        if 'topic' in self.request.GET:
            query_params['topic'] = self.request.GET['topic']
            try:
                topic = int(self.request.GET['topic'])
                topic = Topic.objects.get(pk=topic)
                context['topic'] = topic.name
            except:
                pass

        if 'qanda_search_str' in self.request.GET:
            query_params.update({
                'qanda_search_str': self.request.GET['qanda_search_str'],
                'search_type': self.request.GET.get('search_type', ''),
                'is_simple': self.request.GET.get('is_simple', '')
            })
            context['qanda_search_str'] = self.request.GET['qanda_search_str']

        context['query_params'] = query_params
        
        if self.request.user.has_perm('agony.change_qanda'):
            context['can_edit'] = True
        else:
            context['can_edit'] = False

        return context

class QandADetail(DetailView):
    model = QandA

    def get_context_data(self, **kwargs):
        context = super(QandADetail, self).get_context_data(**kwargs)
        context['qanda_search'] = True
        if self.request.user.has_perm('agony.change_qanda'):
            context['can_edit'] = True
        else:
            context['can_edit'] = False
        return context

    def get_object(self, queryset=None):
        obj = super(QandADetail, self).get_object()
        if obj.is_published() is False:
            if self.request.user.is_staff is True:
                messages.add_message(self.request, messages.INFO,
                                     "This Q&A is not published.")
            else:
                raise Http404
        return obj
