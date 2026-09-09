from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render

from businesses.access import demo_business_read_only, membership_required
from catalogue.forms import ProductCreationForm, ProductUpdateForm
from catalogue.models import Product
from catalogue.services import create_product, deactivate_product, update_product


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
    else:
        stock = "all"
    return render(
        request,
        "catalogue/product_list.html",
        {"products": products, "query": query, "status": status, "stock": stock},
    )


@membership_required
def product_detail(request, product_id):
    product = get_object_or_404(
        Product.objects.prefetch_related("stock_movements__stock_adjustment"),
        pk=product_id,
        business=request.business,
    )
    return render(request, "catalogue/product_detail.html", {"product": product})


@membership_required
@demo_business_read_only
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
            return redirect("product_detail", product_id=product.pk)
    return render(
        request,
        "catalogue/product_form.html",
        {
            "form": form,
            "page_title": "Create Product",
            "submit_label": "Create Product",
            "intro": "Opening quantity is recorded as a traceable Stock Adjustment. Stock on Hand cannot be edited directly.",
        },
    )


@membership_required
@demo_business_read_only
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
@demo_business_read_only
def product_deactivate(request, product_id):
    product = get_object_or_404(Product, pk=product_id, business=request.business)
    if request.method != "POST":
        return redirect("product_detail", product_id=product.pk)
    deactivate_product(business=request.business, actor=request.user, product=product)
    return redirect("product_detail", product_id=product.pk)
