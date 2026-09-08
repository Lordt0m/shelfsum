from django.db import models


class ImmutableQuerySet(models.QuerySet):
    def _reject_mutation(self):
        raise TypeError(self.model.immutable_error)

    def update(self, **kwargs):
        self._reject_mutation()

    def bulk_update(self, objs, fields, batch_size=None):
        self._reject_mutation()

    def delete(self):
        self._reject_mutation()


class ImmutableManager(models.Manager.from_queryset(ImmutableQuerySet)):
    pass


class ImmutableModel(models.Model):
    immutable_error = "Records are immutable."
    objects = ImmutableManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise TypeError(self.immutable_error)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError(self.immutable_error)
