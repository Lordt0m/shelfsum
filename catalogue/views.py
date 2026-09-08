from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render

from businesses.access import demo_business_read_only, membership_required
from catalogue.forms import ProductCreationForm
from catalogue.models import Product
from catalogue.services import create_product


@membership_required
def product_list(request):
    products = Product.objects.filter(business=request.business)
    return render(request, "catalogue/product_list.html", {"products": products})


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
    return render(request, "catalogue/product_form.html", {"form": form})
