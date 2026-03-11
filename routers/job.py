@job_router.post("/packages/callback/hyper")
async def job_hyperpay_callback(
    request: Request,
    background_tasks: BackgroundTasks,
):
    try:
        data: dict = {}

        # Try to collect form data
        try:
            form = await request.form()
            data.update(form)
        except Exception:
            pass

        # Try to collect JSON body
        try:
            body = await request.json()
            if isinstance(body, dict):
                data.update(body)
        except Exception:
            pass

        # Include query params
        data.update(dict(request.query_params))

        # ---------- Encrypted callback ----------
        if "encryptedBody" in data:
            try:
                logger.info("Encrypted JOB webhook received — decrypting payload")
                decrypted = decrypt_hyperpay_payload(data["encryptedBody"])

                # Merge decrypted data so you can inspect it if needed
                if isinstance(decrypted, dict):
                    data.update(decrypted)

                payment_id = decrypted.get("id")
                if payment_id:
                    logger.info(f"Decrypted JOB payment_id={payment_id}, queueing verification")
                    background_tasks.add_task(
                        process_job_payment_by_payment_id,
                        payment_id,
                    )
                else:
                    # Fallback: trigger polling if no direct id
                    logger.info("No payment_id in decrypted payload, starting polling")
                    background_tasks.add_task(poll_pending_job_payments)

            except Exception as e:
                logger.error(f"Failed to decrypt HyperPay payload: {e}")
                # As a safety net, still start polling
                background_tasks.add_task(poll_pending_job_payments)

        # ---------- Plain callback with id ----------
        payment_id = data.get("id")
        if payment_id:
            logger.info(f"Plain JOB webhook with payment_id={payment_id}, queueing verification")
            background_tasks.add_task(
                process_job_payment_by_payment_id,
                payment_id,
            )

    except Exception as e:
        logger.error(f"Callback error: {e}")

    return JSONResponse(status_code=200, content={"status": "received"})
