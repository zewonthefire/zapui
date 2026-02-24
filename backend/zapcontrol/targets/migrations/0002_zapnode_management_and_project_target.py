from django.db import migrations, models


def populate_zapnode_names(apps, schema_editor):
    ZapNode = apps.get_model('targets', 'ZapNode')
    for index, node in enumerate(ZapNode.objects.order_by('id'), start=1):
        node.name = f'zap-node-{index}'
        node.save(update_fields=['name'])


class Migration(migrations.Migration):

    dependencies = [
        ('targets', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='zapnode',
            old_name='is_active',
            new_name='enabled',
        ),
        migrations.RemoveField(
            model_name='zapnode',
            name='is_internal',
        ),
        migrations.AddField(
            model_name='zapnode',
            name='name',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.RunPython(populate_zapnode_names, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='zapnode',
            name='name',
            field=models.CharField(max_length=120, unique=True),
        ),
        migrations.AddField(
            model_name='zapnode',
            name='docker_container_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='zapnode',
            name='last_health_check',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='zapnode',
            name='last_latency_ms',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='zapnode',
            name='managed_type',
            field=models.CharField(choices=[('internal_managed', 'Internal managed'), ('external', 'External')], default='external', max_length=32),
        ),
        migrations.AddField(
            model_name='zapnode',
            name='status',
            field=models.CharField(choices=[('unknown', 'Unknown'), ('healthy', 'Healthy'), ('unreachable', 'Unreachable'), ('disabled', 'Disabled')], default='unknown', max_length=32),
        ),
        migrations.AddField(
            model_name='zapnode',
            name='version',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AlterModelOptions(
            name='zapnode',
            options={'ordering': ('name',)},
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('slug', models.SlugField(unique=True)),
                ('description', models.TextField(blank=True)),
                ('owner', models.CharField(blank=True, max_length=255)),
                ('risk_level', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='medium', max_length=16)),
                ('tags', models.JSONField(blank=True, default=list)),
            ],
            options={'ordering': ('name',)},
        ),
        migrations.CreateModel(
            name='Target',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('base_url', models.URLField()),
                ('environment', models.CharField(choices=[('dev', 'Development'), ('stage', 'Staging'), ('prod', 'Production')], default='dev', max_length=16)),
                ('auth_type', models.CharField(choices=[('none', 'None'), ('basic', 'Basic'), ('bearer', 'Bearer'), ('cookie', 'Cookie')], default='none', max_length=16)),
                ('auth_config', models.JSONField(blank=True, default=dict)),
                ('notes', models.TextField(blank=True)),
                ('project', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='targets', to='targets.project')),
            ],
            options={'ordering': ('project__name', 'name')},
        ),
        migrations.AlterUniqueTogether(
            name='target',
            unique_together={('project', 'name')},
        ),
    ]
