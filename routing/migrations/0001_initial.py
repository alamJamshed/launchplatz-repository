from django.db import migrations, models
import django.db.models.deletion
import routing.validators


def migrate_project_domains(apps, schema_editor):
    Project = apps.get_model('projects', 'Project')
    Domain = apps.get_model('routing', 'Domain')
    Route = apps.get_model('routing', 'Route')
    from routing.validators import normalize_hostname

    claimed = set()
    for project in Project.objects.exclude(domain='').order_by('pk'):
        normalized = normalize_hostname(project.domain)
        if normalized in claimed or Domain.objects.filter(
            normalized_hostname=normalized
        ).exists():
            raise RuntimeError(
                f'Duplicate legacy project domain: {normalized}. '
                'Resolve duplicate Project.domain values before migrating.'
            )
        claimed.add(normalized)
        domain = Domain.objects.create(
            project_id=project.pk,
            hostname=project.domain,
            normalized_hostname=normalized,
        )
        Route.objects.create(
            domain_id=domain.pk,
            service_name=project.django_service_name,
            internal_port=8000,
        )


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('projects', '0004_project_django_service_name'),
        ('servers', '0002_server_last_checked_at_server_last_failure_reason_and_more'),
    ]
    operations = [
        migrations.CreateModel(
            name='Domain',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('hostname', models.CharField(max_length=253)),
                ('normalized_hostname', models.CharField(max_length=253, unique=True)),
                ('dns_status', models.CharField(choices=[('pending', 'Pending'), ('verified', 'Verified'), ('failed', 'Failed')], default='pending', max_length=10)),
                ('dns_last_checked_at', models.DateTimeField(blank=True, null=True)),
                ('resolved_addresses', models.JSONField(blank=True, default=list)),
                ('dns_error', models.CharField(blank=True, max_length=500)),
                ('consecutive_dns_successes', models.PositiveSmallIntegerField(default=0)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to='coreapp.user')),
                ('project', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='routing_domain', to='projects.project')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to='coreapp.user')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Route',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('service_name', models.CharField(max_length=100, validators=[routing.validators.validate_service_name])),
                ('internal_port', models.PositiveIntegerField()),
                ('desired_enabled', models.BooleanField(default=True)),
                ('tls_enabled', models.BooleanField(default=False)),
                ('observed_status', models.CharField(choices=[('pending', 'Pending'), ('configured', 'Configured'), ('healthy', 'Healthy'), ('failed', 'Failed'), ('disabled', 'Disabled')], default='pending', max_length=12)),
                ('configuration_revision', models.CharField(blank=True, max_length=64)),
                ('last_reconciled_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.CharField(blank=True, max_length=500)),
                ('lease_owner', models.CharField(blank=True, max_length=64)),
                ('lease_expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to='coreapp.user')),
                ('domain', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='route', to='routing.domain')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to='coreapp.user')),
            ],
        ),
        migrations.CreateModel(
            name='ServerRoutingLease',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('owner', models.CharField(blank=True, max_length=64)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('server', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='routing_lease', to='servers.server')),
            ],
        ),
        migrations.CreateModel(
            name='ReconciliationEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('configured', 'Configured'), ('healthy', 'Healthy'), ('failed', 'Failed'), ('disabled', 'Disabled')], max_length=12)),
                ('revision', models.CharField(blank=True, max_length=64)),
                ('error', models.CharField(blank=True, max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reconciliation_events', to='routing.route')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='route',
            constraint=models.CheckConstraint(
                condition=models.Q(internal_port__gte=1, internal_port__lte=65535),
                name='routing_valid_internal_port',
            ),
        ),
        migrations.RunPython(migrate_project_domains, migrations.RunPython.noop),
    ]
