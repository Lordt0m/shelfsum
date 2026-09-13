from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from businesses.access import demo_business_read_only, membership_required
from catalogue.models import Product
from .forms import StockAdjustmentForm
from .models import StockAdjustment
from .services import record_stock_adjustment


@membership_required
def adjustment_list(request):
    adjustments = StockAdjustment.objects.filter(
        business=request.business
    ).select_related("product")
    reason = request.GET.get("reason", "")
    manual_reasons = {
        value
        for value, _ in StockAdjustment.Reason.choices
        if value != StockAdjustment.Reason.OPENING
    }
    if reason in manual_reasons:
        adjustments = adjustments.filter(reason=reason)
    else:
        reason = ""
    date_from, date_to = request.GET.get("date_from", ""), request.GET.get("date_to", "")
    filter_error = ""
    try:
        parsed_from, parsed_to = parse_date(date_from) if date_from else None, parse_date(date_to) if date_to else None
    except ValueError:
        parsed_from = parsed_to = None
        filter_error = "Enter valid calendar dates."
    if date_from and parsed_from is None and not filter_error:
        filter_error = "Enter a valid start date."
    if date_to and parsed_to is None and not filter_error:
        filter_error = "Enter a valid end date."
    if parsed_from:
        adjustments = adjustments.filter(created_at__date__gte=parsed_from)
    if parsed_to:
        adjustments = adjustments.filter(created_at__date__lte=parsed_to)
    return render(request, "inventory/adjustment_list.html", {
        "adjustments": adjustments, "reason": reason,
        "reason_choices": [(v, l) for v, l in StockAdjustment.Reason.choices if v != StockAdjustment.Reason.OPENING],
        "date_from": date_from, "date_to": date_to, "filter_error": filter_error,
    })


@membership_required
def adjustment_detail(request, adjustment_id):
    adjustment = get_object_or_404(
        StockAdjustment.objects.select_related("product"),
        pk=adjustment_id,
        business=request.business,
    )
    return render(request, "inventory/adjustment_detail.html", {"adjustment": adjustment})


@membership_required
@demo_business_read_only
def adjustment_create(request):
    form = StockAdjustmentForm(request.POST or None, business=request.business)
    preview = None
    if form.is_valid():
        product = form.cleaned_data["product"]
        preview = product.stock_on_hand + form.cleaned_data["quantity_change"]
        if preview < 0:
            form.add_error("quantity_change", "This change would make Stock on Hand negative.")
            preview = None
        elif request.method == "POST" and request.POST.get("action") == "record":
            try:
                adjustment = record_stock_adjustment(business=request.business, actor=request.user, product=product, quantity_change=form.cleaned_data["quantity_change"], reason=form.cleaned_data["reason"], notes=form.cleaned_data["notes"])
            except ValidationError as error:
                form.add_error(None, error)
            else:
                return redirect("adjustment_detail", adjustment_id=adjustment.pk)
    return render(request, "inventory/adjustment_form.html", {
        "form": form, "preview": preview, "page_title": "Record Stock Adjustment",
    })
