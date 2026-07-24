from celery import shared_task

from .models import Route
from .services import RoutingOperationError, reconcile_route, verify_domain_dns


@shared_task(
    bind=True,
    name='routing.reconcile_route',
    autoretry_for=(RoutingOperationError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def reconcile_route_task(self, route_id):
    return reconcile_route(route_id, owner=self.request.id)


@shared_task(name='routing.reconcile_all_routes')
def reconcile_all_routes():
    for route_id in Route.objects.filter(
        is_active=True, is_deleted=False
    ).values_list('pk', flat=True):
        reconcile_route_task.delay(route_id)


@shared_task(name='routing.verify_all_domains')
def verify_all_domains():
    routes = Route.objects.select_related(
        'domain__project__server'
    ).filter(is_active=True, is_deleted=False, desired_enabled=True)
    for route in routes:
        verify_domain_dns(route.domain)
