from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from businesses.access import demo_business_read_only, membership_required
from .forms import ExpenseForm
from .models import Expense
from .services import correct_expense, record_expense, void_expense

@membership_required
def expense_list(request):
    expenses = Expense.objects.filter(business=request.business)
    status = request.GET.get("status", "")
    if status in dict(Expense.Status.choices): expenses = expenses.filter(status=status)
    else: status = ""
    date_from, date_to, filter_error = request.GET.get("date_from", ""), request.GET.get("date_to", ""), ""
    if date_from:
        try:
            parsed = parse_date(date_from)
        except ValueError:
            parsed = None
        if parsed: expenses = expenses.filter(date__gte=parsed)
        else: filter_error = "Enter a valid start date."
    if date_to:
        try:
            parsed = parse_date(date_to)
        except ValueError:
            parsed = None
        if parsed: expenses = expenses.filter(date__lte=parsed)
        else: filter_error = "Enter a valid end date."
    return render(request, "expenses/expense_list.html", {"expenses": expenses, "status": status, "status_choices": Expense.Status.choices, "date_from": date_from, "date_to": date_to, "filter_error": filter_error})

@membership_required
@demo_business_read_only
def expense_create(request):
    form = ExpenseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        return redirect("expense_detail", expense_id=record_expense(business=request.business, actor=request.user, details=form.cleaned_data).pk)
    return render(request, "expenses/expense_form.html", {"form": form, "page_title": "Record Expense"})

@membership_required
def expense_detail(request, expense_id):
    expense = get_object_or_404(Expense, pk=expense_id, business=request.business)
    return render(request, "expenses/expense_detail.html", {"expense": expense})

@membership_required
@demo_business_read_only
def expense_void(request, expense_id):
    expense = get_object_or_404(Expense, pk=expense_id, business=request.business)
    if request.method != "POST": return render(request, "expenses/expense_detail.html", {"expense": expense}, status=405)
    try: void_expense(business=request.business, actor=request.user, expense=expense)
    except ValidationError as error: return render(request, "expenses/expense_detail.html", {"expense": expense, "error": error}, status=400)
    return redirect("expense_detail", expense_id=expense.pk)

@membership_required
@demo_business_read_only
def expense_correct(request, expense_id):
    original = get_object_or_404(Expense, pk=expense_id, business=request.business)
    initial = {f: getattr(original, f) for f in ["date", "category", "description", "amount", "notes"]}
    form = ExpenseForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try: replacement = correct_expense(business=request.business, actor=request.user, expense=original, details=form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
            return render(request, "expenses/expense_form.html", {"form": form, "page_title": "Correct Expense", "original": original}, status=400)
        else: return redirect("expense_detail", expense_id=replacement.pk)
    return render(request, "expenses/expense_form.html", {"form": form, "page_title": "Correct Expense", "original": original})
