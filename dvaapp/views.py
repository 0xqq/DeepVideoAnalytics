from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse,JsonResponse,HttpResponseRedirect
import requests
import os,base64
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView,DetailView
from django.utils.decorators import method_decorator
from .forms import UploadFileForm
from .models import Video,Frame,Detection,Query,QueryResults,TEvent
from .tasks import extract_frames,query_by_image


def search(request):
    if request.method == 'POST':
        query = Query()
        query.save()
        primary_key = query.pk
        image_url = request.POST.get('image_url')
        image_data = base64.decodestring(image_url[22:])
        query_path = "{}/queries/{}.png".format(settings.MEDIA_ROOT,primary_key)
        with open(query_path,'w') as fh:
            fh.write(image_data)
        result = query_by_image.apply_async(args=[primary_key],queue=settings.Q_INDEXER)
        query.task_id = result.task_id
        query.save()
        results = []
        entries = result.get()
        if entries:
            for algo,rlist in entries.iteritems():
                for r in rlist:
                    r['url'] = '/media/{}/frames/{}.jpg'.format(r['video_primary_key'],r['time_seconds'])
                    results.append(r)
        return JsonResponse(data={'task_id':result.task_id,'primary_key':primary_key,'results':results})



def index(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            handle_uploaded_file(request.FILES['file'],form.cleaned_data['name'])
        else:
            raise ValueError
    else:
        form = UploadFileForm()
    context = { 'form' : form }
    context['video_count'] = Video.objects.count()
    context['frame_count'] = Frame.objects.count()
    context['query_count'] = Query.objects.count()
    context['detection_count'] = Detection.objects.count()
    return render(request, 'dashboard.html', context)


def handle_uploaded_file(f,name,extract=True):
    video = Video()
    video.name = name
    video.save()
    os.mkdir('{}/{}'.format(settings.MEDIA_ROOT,video.pk))
    os.mkdir('{}/{}/video/'.format(settings.MEDIA_ROOT,video.pk))
    os.mkdir('{}/{}/frames/'.format(settings.MEDIA_ROOT,video.pk))
    os.mkdir('{}/{}/indexes/'.format(settings.MEDIA_ROOT, video.pk))
    os.mkdir('{}/{}/detections/'.format(settings.MEDIA_ROOT, video.pk))
    os.mkdir('{}/{}/audio/'.format(settings.MEDIA_ROOT, video.pk))
    primary_key = video.pk
    filename = f.name
    if filename.endswith('.mp4') or filename.endswith('.flv') or filename.endswith('.zip'):
        with open('{}/{}/video/{}.{}'.format(settings.MEDIA_ROOT,video.pk,video.pk,filename.split('.')[-1]), 'wb+') as destination:
            for chunk in f.chunks():
                destination.write(chunk)
        video.uploaded = True
        if filename.endswith('.zip'):
            video.dataset = True
        video.save()
        if extract:
            extract_frames.apply_async(args=[primary_key],queue=settings.Q_EXTRACTOR)
    else:
        raise ValueError,"Extension {} not allowed".format(filename.split('.')[-1])

class VideoList(ListView):
    model = Video
    paginate_by = 100


class VideoDetail(DetailView):
    model = Video

    def get_context_data(self, **kwargs):
        context = super(VideoDetail, self).get_context_data(**kwargs)
        context['frame_list'] = Frame.objects.all().filter(video=self.object)
        context['detection_list'] = Detection.objects.all().filter(video=self.object)
        context['url'] = '{}/{}/video/{}.mp4'.format(settings.MEDIA_URL,self.object.pk,self.object.pk)
        return context

class QueryList(ListView):
    model = Query


class QueryDetail(DetailView):
    model = Query

    def get_context_data(self, **kwargs):
        context = super(QueryDetail, self).get_context_data(**kwargs)
        context['result_list'] = QueryResults.objects.all().filter(query=self.object)
        context['url'] = '{}/queries/{}.png'.format(settings.MEDIA_URL,self.object.pk,self.object.pk)
        return context


class FrameList(ListView):
    model = Frame


class FrameDetail(DetailView):
    model = Frame

    def get_context_data(self, **kwargs):
        context = super(FrameDetail, self).get_context_data(**kwargs)
        context['detection_list'] = Detection.objects.all().filter(frame=self.object)
        context['video'] = self.object.video
        context['url'] = '{}/{}/frames/{}.jpg'.format(settings.MEDIA_URL,self.object.video.pk,self.object.time_seconds)
        return context



def status(request):
    context = { }
    context['video_count'] = Video.objects.count()
    context['frame_count'] = Frame.objects.count()
    context['query_count'] = Query.objects.count()
    context['events'] = TEvent.objects.all()
    context['detection_count'] = Detection.objects.count()
    try:
        context['indexer_log'] = file("logs/qindexer.log").read()
    except:
        context['indexer_log'] = ""
    try:
        context['detector_log'] = file("logs/qdetector.log").read()
    except:
        context['detector_log'] = ""
    try:
        context['extract_log'] = file("logs/qextract.log").read()
    except:
        context['extract_log'] = ""
    try:
        context['fab_log'] = file("logs/fab.log").read()
    except:
        context['fab_log'] = ""
    return render(request, 'status.html', context)