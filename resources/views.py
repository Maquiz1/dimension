import mimetypes

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from study.access import staff_required

from .forms import StudyDocumentForm
from .models import StudyDocument


def _permissions(user):
    return {
        'can_add': user.has_perm('resources.add_studydocument'),
        'can_change': user.has_perm('resources.change_studydocument'),
        'can_delete': user.has_perm('resources.delete_studydocument'),
    }


@method_decorator(staff_required, name='dispatch')
class DocumentListView(ListView):
    model = StudyDocument
    template_name = 'resources/list.html'
    context_object_name = 'documents'
    paginate_by = 25

    def get_queryset(self):
        qs = StudyDocument.objects.select_related('uploaded_by')
        category = self.request.GET.get('category')
        if category in dict(StudyDocument.CATEGORY_CHOICES):
            qs = qs.filter(category=category)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(version__icontains=q))
        return qs.order_by('-updated_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counts = dict(StudyDocument.objects.values_list('category').annotate(n=Count('id')))
        context['tabs'] = [(key, label, counts.get(key, 0)) for key, label in StudyDocument.CATEGORY_CHOICES]
        context['total_count'] = sum(counts.values())
        context['category'] = self.request.GET.get('category', '')
        context['q'] = self.request.GET.get('q', '')
        params = self.request.GET.copy()
        params.pop('page', None)
        context['query_string'] = params.urlencode()
        context.update(_permissions(self.request.user))
        return context


@method_decorator(staff_required, name='dispatch')
class DocumentDetailView(DetailView):
    model = StudyDocument
    template_name = 'resources/detail.html'
    context_object_name = 'document'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_permissions(self.request.user))
        return context


@method_decorator(staff_required, name='dispatch')
class DocumentCreateView(PermissionRequiredMixin, CreateView):
    model = StudyDocument
    form_class = StudyDocumentForm
    template_name = 'resources/form.html'
    permission_required = 'resources.add_studydocument'

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, f'“{form.instance.title}” was uploaded.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('resources:detail', args=[self.object.pk])


@method_decorator(staff_required, name='dispatch')
class DocumentUpdateView(PermissionRequiredMixin, UpdateView):
    model = StudyDocument
    form_class = StudyDocumentForm
    template_name = 'resources/form.html'
    permission_required = 'resources.change_studydocument'

    def form_valid(self, form):
        # A new file replaces the old one: remove the old file from storage.
        old = StudyDocument.objects.get(pk=self.object.pk).file
        if 'file' in form.changed_data:
            form.instance.uploaded_by = self.request.user
        response = super().form_valid(form)
        if 'file' in form.changed_data and old and old.name != self.object.file.name:
            old.storage.delete(old.name)
        messages.success(self.request, f'“{self.object.title}” was updated.')
        return response

    def get_success_url(self):
        return reverse('resources:detail', args=[self.object.pk])


@method_decorator(staff_required, name='dispatch')
class DocumentDeleteView(PermissionRequiredMixin, DeleteView):
    model = StudyDocument
    template_name = 'resources/confirm_delete.html'
    context_object_name = 'document'
    permission_required = 'resources.delete_studydocument'
    success_url = reverse_lazy('resources:list')

    def form_valid(self, form):
        document = self.get_object()
        if document.file:
            document.file.storage.delete(document.file.name)
        messages.success(self.request, f'“{document.title}” was deleted.')
        return super().form_valid(form)


@method_decorator(staff_required, name='dispatch')
class DocumentFileView(View):
    """Serve files through the app, to logged-in staff only. Uploads have no public URL.
    as_attachment False shows a PDF in the page; any other type is always downloaded."""

    as_attachment = True

    def get(self, request, pk):
        document = get_object_or_404(StudyDocument, pk=pk)
        if not document.file or not document.file.storage.exists(document.file.name):
            raise Http404('This document’s file is missing. Ask an administrator to upload it again.')
        inline = not self.as_attachment and document.is_pdf
        response = FileResponse(
            document.file.open('rb'),
            content_type=mimetypes.guess_type(document.file.name)[0] or 'application/octet-stream',
            as_attachment=not inline,
            filename=document.download_name,
        )
        response['X-Content-Type-Options'] = 'nosniff'
        return response


@method_decorator(xframe_options_sameorigin, name='dispatch')
class DocumentPreviewView(DocumentFileView):
    as_attachment = False
