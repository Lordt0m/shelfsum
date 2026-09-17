from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from businesses.access import membership_required
from sales.forms import SaleForm, SaleLineFormSet
from sales.models import Sale
from sales.services import complete_sale, create_draft_sale, save_draft_sale, void_sale


def _sale_post_data(request):
    post_data = request.POST.copy()
    if request.POST.get("add_line"):
        try:
            total_forms = int(post_data.get("lines-TOTAL_FORMS", 0))
        except (TypeError, ValueError):
            return post_data
        post_data["lines-TOTAL_FORMS"] = str(total_forms + 1)
    return post_data


def _draft_line_data(formset):
    return [form.cleaned_data for form in formset.forms if form.cleaned_data and not form.cleaned_data.get("DELETE")]


@membership_required
def sale_list(request):
    sales = Sale.objects.filter(business=request.business)
    status = request.GET.get("status", "")
    if status in dict(Sale.Status.choices):
        sales = sales.filter(status=status)
    else:
        status = ""
    date_from, date_to, filter_error = request.GET.get("date_from", ""), request.GET.get("date_to", ""), ""
    if date_from:
        parsed = parse_date(date_from)
        if parsed is None: filter_error = "Enter a valid start date."
        else: sales = sales.filter(sale_date__gte=parsed)
    if date_to:
        parsed = parse_date(date_to)
        if parsed is None: filter_error = "Enter a valid end date."
        else: sales = sales.filter(sale_date__lte=parsed)
    return render(request, "sales/sale_list.html", {"sales": sales, "status": status, "status_choices": Sale.Status.choices, "date_from": date_from, "date_to": date_to, "filter_error": filter_error})


@membership_required
def sale_create(request):
    sale = Sale(business=request.business, creator=request.user)
    post_data = _sale_post_data(request) if request.method == "POST" else None
    form = SaleForm(post_data, instance=sale)
    formset = SaleLineFormSet(post_data, instance=sale, form_kwargs={"business": request.business})
    if request.method == "POST" and not request.POST.get("add_line") and form.is_valid() and formset.is_valid():
        if not _draft_line_data(formset):
            form.add_error(None, "Add at least one Product line.")
        else:
            try:
                sale = create_draft_sale(
                    business=request.business,
                    actor=request.user,
                    form=form,
                    formset=formset,
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                return redirect("sale_detail", sale_id=sale.pk)
    return render(request, "sales/sale_form.html", {"form": form, "formset": formset})


@membership_required
def sale_detail(request, sale_id):
    sale = get_object_or_404(Sale.objects.prefetch_related("lines__product"), pk=sale_id, business=request.business)
    if request.method == "POST" and sale.status != Sale.Status.DRAFT:
        return render(request, "sales/sale_detail.html", {"sale": sale, "error": "This Sale has already been completed."}, status=400)
    if request.method == "POST":
        try: complete_sale(business=request.business, actor=request.user, sale=sale)
        except ValidationError as error: return render(request, "sales/sale_detail.html", {"sale": sale, "error": error}, status=400)
        return redirect("sale_detail", sale_id=sale.pk)
    return render(request, "sales/sale_detail.html", {"sale": sale})


@membership_required
def sale_void(request, sale_id):
    sale = get_object_or_404(
        Sale.objects.prefetch_related("lines__product"),
        pk=sale_id,
        business=request.business,
    )
    if request.method == "GET":
        if sale.status != Sale.Status.COMPLETED:
            return redirect("sale_detail", sale_id=sale.pk)
        return render(request, "sales/sale_void_confirm.html", {"sale": sale})
    if request.method != "POST":
        return render(request, "sales/sale_void_confirm.html", {"sale": sale}, status=405)
    try:
        void_sale(business=request.business, actor=request.user, sale=sale)
    except ValidationError as error:
        return render(request, "sales/sale_detail.html", {"sale": sale, "error": error}, status=400)
    return redirect("sale_detail", sale_id=sale.pk)


@membership_required
def sale_edit(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id, business=request.business)
    if sale.status != Sale.Status.DRAFT: return redirect("sale_detail", sale_id=sale.pk)
    post_data = _sale_post_data(request) if request.method == "POST" else None
    form = SaleForm(post_data, instance=sale)
    formset = SaleLineFormSet(post_data, instance=sale, form_kwargs={"business": request.business})
    if request.method == "POST" and not request.POST.get("add_line") and form.is_valid() and formset.is_valid():
        if not _draft_line_data(formset): form.add_error(None, "Add at least one Product line.")
        else:
            try:
                save_draft_sale(
                    business=request.business,
                    actor=request.user,
                    sale=sale,
                    form=form,
                    formset=formset,
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                return redirect("sale_detail", sale_id=sale.pk)
    return render(request, "sales/sale_form.html", {"form": form, "formset": formset, "sale": sale})
