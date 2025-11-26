import click
import frappe
from frappe.commands import get_site, pass_context
from frappe.utils import update_progress_bar


@click.command("upload-to-s3", help="Upload existing files to S3 External Storage")
@click.option("--batch-size", default=1000, help="Number of files to process per batch.")
@click.option("--limit", default=0, help="Total max files to process (0 = no limit).")
@pass_context
def upload_to_s3(context, batch_size, limit):
    site = get_site(context)
    frappe.init(site=site)
    frappe.connect()

    if not frappe.db.exists("DFP External Storage", {"enabled": 1}):
        click.echo("S3 External Storage is not configured/enabled.", err=True)
        return

    filters = {"dfp_external_storage": ["is", "not set"]}

    total_available = frappe.db.count("File", filters=filters)

    if not total_available:
        click.echo("No files pending upload.")
        return

    # Apply limit if provided
    total_to_process = limit if limit > 0 else total_available
    total_to_process = min(total_to_process, total_available)

    click.echo(f"Files available: {total_available}")
    click.echo(f"Files to process: {total_to_process}")

    failed_ids = []
    processed = 0

    while processed < total_to_process:
        batch_limit = min(batch_size, total_to_process - processed)

        files = frappe.get_all(
            "File",
            pluck="name",
            filters=filters,
            limit_start=processed,
            limit_page_length=batch_limit,
        )

        for index, file_name in enumerate(files, start=1):
            try:
                doc = frappe.get_doc("File", file_name)
                doc.dfp_external_storage_upload_file()
                doc.save()
                frappe.db.commit()
            except Exception:
                failed_ids.append(file_name)
                click.echo(f"Failed to upload: {file_name}", err=True)

            update_progress_bar("Uploading files to S3...", processed + index, total_to_process)

        processed += len(files)

    if failed_ids:
        frappe.log_error(
            title="Failed to upload files to S3",
            message=frappe.as_json(failed_ids, indent=2),
        )

    frappe.destroy()
    print()


commands = [upload_to_s3]
