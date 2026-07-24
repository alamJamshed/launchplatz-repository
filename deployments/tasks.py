from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

from .models import Deployment
from .services import DeploymentRunner


@shared_task(bind=True, name='deployments.run_deployment')
def run_deployment(self, deployment_id):
    deployment = Deployment.objects.select_related(
        'project__server', 'triggered_by'
    ).get(pk=deployment_id)
    if deployment.status not in {
        Deployment.Status.PENDING, Deployment.Status.CANCELLING,
    }:
        return deployment.status
    if not deployment.celery_task_id:
        deployment.celery_task_id = self.request.id or ''
        deployment.save(update_fields=['celery_task_id'])
    DeploymentRunner(deployment).run()
    deployment.refresh_from_db(fields=['status'])
    if deployment.status == Deployment.Status.SUCCESS:
        try:
            route = deployment.project.routing_domain.route
        except (AttributeError, ObjectDoesNotExist):
            route = None
        if route and route.desired_enabled:
            from routing.tasks import reconcile_route_task
            reconcile_route_task.delay(route.pk)
    return deployment.status
