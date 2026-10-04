from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render

from businesses.access import membership_required
from catalogue.forms import ProductCreationForm, ProductUpdateForm
from catalogue.models import Product
from catalogue.services import create_product, deactivate_product, update_product
from inventory.history import movement_history_date_params, movement_history_queryset
from reports.movement import MovementReportRow


@membership_required
def product_list(request):
    products = Product.objects.filter(business=request.business)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "active")
    stock = request.GET.get("stock", "all")
    if query:
        products = products.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    if status == "inactive":
        products = products.filter(is_active=False)
    elif status != "all":
        status = "active"
        products = products.filter(is_active=True)
    if stock == "low":
        products = products.filter(stock_on_hand__lte=F("low_stock_threshold"))
    elif stock == "out":
        products = products.filter(stock_on_hand=0)
    elif stock == "healthy":
        products = products.filter(stock_on_hand__gt=F("low_stock_threshold"))
    else:
        stock = "all"
    page_obj = Paginator(products, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "catalogue/product_list.html",
        {"products": page_obj.object_list, "page_obj": page_obj, "query": query,
         "status": status, "stock": stock,
         "filter_query": urlencode({"q": query, "status": status, "stock": stock})},
    )


@membership_required
def product_detail(request, product_id):
    product = get_object_or_404(
        Product.objects.all(),
        pk=product_id,
        business=request.business,
    )
    history = movement_history_queryset(business=request.business).filter(product=product)
    page_number = request.GET.get("page")
    # Reversal links can target an original outside the first history page.
    target_id = request.GET.get("movement", "")
    if target_id.isascii() and target_id.isdecimal() and len(target_id) <= 18:
        target = history.filter(pk=int(target_id)).first()
        if target:
            position = history.filter(Q(created_at__gt=target.created_at) | Q(created_at=target.created_at, pk__gt=target.pk)).count()
            page_number = position // 25 + 1
    page_obj = Paginator(history, 25).get_page(page_number)
    movements = tuple(MovementReportRow(movement=row) for row in page_obj.object_list)
    history_query = urlencode({"product": product.pk, **movement_history_date_params(history)})
    return render(request, "catalogue/product_detail.html", {"product": product, "movements": movements, "page_obj": page_obj, "history_query": history_query})


@membership_required
def product_create(request):
    form = ProductCreationForm(request.POST or None, business=request.business)
    if request.method == "POST" and form.is_valid():
        try:
            product = create_product(
                business=request.business,
                actor=request.user,
                details=form.to_product_creation(),
            )
        except IntegrityError:
            form.add_error(
                None,
                "A Product with the same name or SKU already exists in this Business.",
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Product added. Opening stock is recorded in its movement history.")
            return redirect("product_detail", product_id=product.pk)
    return render(
        request,
        "catalogue/product_form.html",
        {
            "form": form,
            "page_title": "Add product",
            "submit_label": "Add product",
            "intro": "Opening quantity is recorded as a traceable Stock Adjustment. Stock on Hand cannot be edited directly.",
        },
    )


@membership_required
def product_edit(request, product_id):
    product = get_object_or_404(Product, pk=product_id, business=request.business)
    form = ProductUpdateForm(
        request.POST or None, instance=product, business=request.business
    )
    if request.method == "POST" and form.is_valid():
        try:
            update_product(
                business=request.business,
                actor=request.user,
                product=product,
                details=form.to_product_update(),
            )
        except IntegrityError:
            form.add_error(None, "A Product with the same name or SKU already exists.")
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Product details updated.")
            return redirect("product_detail", product_id=product.pk)
    return render(
        request,
        "catalogue/product_form.html",
        {
            "form": form,
            "page_title": "Edit Product",
            "submit_label": "Save changes",
            "intro": "Update catalogue details while the Product's Stock on Hand and movement history remain unchanged.",
        },
    )


@membership_required
def product_deactivate(request, product_id):
    product = get_object_or_404(Product, pk=product_id, business=request.business)
    if request.method != "POST":
        return redirect("product_detail", product_id=product.pk)
    deactivate_product(business=request.business, actor=request.user, product=product)
    messages.success(request, "Product deactivated. Its stock and history are preserved.")
    return redirect("product_detail", product_id=product.pk)
