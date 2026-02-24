from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='AppSetting',
            new_name='Setting',
        ),
        migrations.AlterModelOptions(
            name='setting',
            options={'verbose_name': 'Setting', 'verbose_name_plural': 'Settings'},
        ),
        migrations.AddField(
            model_name='setupstate',
            name='current_step',
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='setupstate',
            name='pool_applied',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='setupstate',
            name='pool_warning',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='setupstate',
            name='wizard_data',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
