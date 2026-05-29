from django.db import models

from django.db import models

class Group(models.Model):
    name = models.CharField(max_length=100)
    time = models.CharField(max_length=10, default="15:00")
    days = models.CharField(max_length=20, default="DCHJ")
    course_type = models.CharField(max_length=100, blank=True)
    teacher = models.CharField(max_length=100, blank=True)
    price = models.IntegerField(default=500000)
    max_students = models.IntegerField(default=17)

    def __str__(self):
        return self.name

class Student(models.Model):
    name = models.CharField(max_length=200)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)
    original_debt = models.IntegerField(default=500000)
    debt_amount = models.IntegerField(default=500000)
    paid_amount = models.IntegerField(default=0)
    payment_status = models.CharField(max_length=20, default="debt")

    def save(self, *args, **kwargs):
        self.debt_amount = max(0, self.original_debt - self.paid_amount)
        self.payment_status = "paid" if self.debt_amount == 0 else "debt"
        super().save(*args, **kwargs)

class Payment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    amount = models.IntegerField()
    month = models.CharField(max_length=20)
    year = models.IntegerField()
    date = models.CharField(max_length=20)

class Trash(models.Model):
    student_data = models.JSONField()
    deleted_at = models.DateTimeField(auto_now_add=True)
    from_group = models.CharField(max_length=100, blank=True)