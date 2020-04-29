# Generated by Django 2.2.9 on 2020-02-18 13:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('geocontrib', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attachment',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='geocontrib.Project'),
        ),
        migrations.AlterField(
            model_name='comment',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='geocontrib.Project'),
        ),
    ]
