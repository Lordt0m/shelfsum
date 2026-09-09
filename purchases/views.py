from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from businesses.access import demo_business_read_only, membership_required
from purchases.forms import PurchaseForm, PurchaseLineFormSet
from purchases.models import Purchase
from purchases.services import complete_purchase


def _draft_line_data(formset):
    return [
        form.cleaned_data
        for form in formset.forms
        if form.cleaned_data and not form.cleaned_data.get("DELETE")
    ]


def _purchase_post_data(request):
    """Add a server-rendered line when JavaScript is unavailable."""
    post_data = request.POST.copy()
    if request.POST.get("add_line"):
        try:
            total_forms = int(post_data.get("lines-TOTAL_FORMS", 0))
        except (TypeError, ValueError):
            return post_data
        if total_forms >= 0:
            post_data["lines-TOTAL_FORMS"] = str(total_forms + 1)
    return post_data


@membership_required
def purchase_list(request):
    purchases = Purchase.objects.filter(business=request.business)
    status = request.GET.get("status", "")
    if status in dict(Purchase.Status.choices):
        purchases = purchases.filter(status=status)
    else:
        status = ""

    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    filter_error = ""
    if date_from:
        parsed_date_from = parse_date(date_from)
        if parsed_date_from is None:
            filter_error = "Enter a valid start date."
        else:
            purchases = purchases.filter(purchase_date__gte=parsed_date_from)
    if date_to:
        parsed_date_to = parse_date(date_to)
        if parsed_date_to is None:
            filter_error = "Enter a valid end date."
        else:
            purchases = purchases.filter(purchase_date__lte=parsed_date_to)

    return render(
        request,
        "purchases/purchase_list.html",
        {
            "purchases": purchases,
            "status": status,
            "status_choices": Purchase.Status.choices,
            "date_from": date_from,
            "date_to": date_to,
            "filter_error": filter_error,
        },
    )


@membership_required
@demo_business_read_only
def purchase_create(request):
    purchase = Purchase(business=request.business, creator=request.user)
    post_data = _purchase_post_data(request) if request.method == "POST" else None
    form = PurchaseForm(post_data, instance=purchase)
    formset = PurchaseLineFormSet(
        post_data,
        instance=purchase,
        form_kwargs={"business": request.business},
    )
    if (
        request.method == "POST"
        and not request.POST.get("add_line")
        and form.is_valid()
        and formset.is_valid()
    ):
        if not _draft_line_data(formset):
            form.add_error(None, "Add at least one Product line.")
        else:
            purchase = form.save(commit=False)
            purchase.business = request.business
            purchase.creator = request.user
            purchase.save()
            formset.instance = purchase
            formset.save()
            return redirect("purchase_detail", purchase_id=purchase.pk)

    return render(
        request,
        "purchases/purchase_form.html",
        {"form": form, "formset": formset},
    )


@membership_required
@demo_business_read_only
def purchase_detail(request, purchase_id):
    purchase = get_object_or_404(
        Purchase.objects.prefetch_related("lines__product"),
        pk=purchase_id,
        business=request.business,
    )
    if request.method == "POST" and purchase.status != Purchase.Status.DRAFT:
        return render(
            request,
            "purchases/purchase_detail.html",
            {
                "purchase": purchase,
                "error": "This Purchase has already been completed.",
            },
            status=400,
        )
    if request.method == "POST":
        try:
            complete_purchase(
                business=request.business,
                actor=request.user,
                purchase=purchase,
            )
        except ValidationError as error:
            return render(
                request,
                "purchases/purchase_detail.html",
                {"purchase": purchase, "error": error},
                status=400,
            )
        return redirect("purchase_detail", purchase_id=purchase.pk)
    return render(request, "purchases/purchase_detail.html", {"purchase": purchase})


@membership_required
@demo_business_read_only
def purchase_edit(request, purchase_id):
    purchase = get_object_or_404(
        Purchase, pk=purchase_id, business=request.business
    )
    if purchase.status != Purchase.Status.DRAFT:
        return redirect("purchase_detail", purchase_id=purchase.pk)

    post_data = _purchase_post_data(request) if request.method == "POST" else None
    form = PurchaseForm(post_data, instance=purchase)
    formset = PurchaseLineFormSet(
        post_data,
        instance=purchase,
        form_kwargs={"business": request.business},
    )
    if (
        request.method == "POST"
        and not request.POST.get("add_line")
        and form.is_valid()
        and formset.is_valid()
    ):
        if not _draft_line_data(formset):
            form.add_error(None, "Add at least one Product line.")
        else:
            form.save()
            formset.save()
            return redirect("purchase_detail", purchase_id=purchase.pk)

    return render(
        request,
        "purchases/purchase_form.html",
        {"form": form, "formset": formset, "purchase": purchase},
    )
