# app.py (handle_payment_success 함수와 stripe_webhook 일부만 변경)

# ... (위쪽 코드 동일)

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        raise HTTPException(status_code=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session['metadata']['user_id'])
        bot_name = session['metadata'].get('bot_name', 'unknown')
        plan = session['metadata'].get('plan', 'unknown')
        # username을 metadata에서 가져오거나, fallback으로 user_id 사용
        username = session['metadata'].get('username', f"user_{user_id}")
        now = datetime.datetime.utcnow()
        if plan == 'lifetime':
            is_lifetime = True
            expiry = None
        else:
            is_lifetime = False
            expiry = now + datetime.timedelta(
                days=30 if plan == 'monthly' else 7 if plan == 'weekly' else 0
            )
        # amount_map은 유지하되, 알림은 무조건 보내기 위해 amount 계산은 옵션
        amount_map = {
            "letmebot": {"weekly": 10, "monthly": 20, "lifetime": 50},
            "morevids": {"weekly": 10, "monthly": 20, "lifetime": 50},
            "onlytrns": {"lifetime": 25},
            "tswrld": {"lifetime": 21},
        }
        amount = amount_map.get(bot_name, {}).get(plan, 0)
        await handle_payment_success(
            user_id, username, session, is_lifetime, expiry, bot_name, plan, amount
        )

    return "", 200

async def handle_payment_success(user_id, username, session, is_lifetime, expiry, bot_name, plan, amount):
    pool = await get_pool()
    try:
        await add_member(
            pool, user_id, username,
            session.get('customer'), session.get('subscription'),
            is_lifetime, expiry, bot_name
        )
        await log_action(pool, user_id, f'payment_stripe_{plan}', amount, bot_name)

        # 사용자에게 성공 메시지
        app_info = next(
            (a for a in applications.values() if a["bot_instance"].bot_name == bot_name),
            None
        )
        if app_info:
            bot = app_info["app"].bot
            link, expiry_str = await create_invite_link(bot)
            await bot.send_message(
                user_id,
                f"🎉 Payment successful!\n\nYour invite link (expires {expiry_str}):\n{link}\n\nWelcome!"
            )

        # ★★★ 관리자에게 알림 ★★★ (모든 봇에 무조건 보내기 + @username 표시)
        plan_type = plan.capitalize()
        payment_date = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        expire_date = "Permanent" if is_lifetime else (expiry.strftime('%Y-%m-%d') if expiry else "N/A")
        admin_text = (
            f"🔔 New Stripe Payment!\n\n"
            f"User ID: {user_id}\n"
            f"Username: @{username.lstrip('@') if username.startswith('@') else username}\n"  # @ 붙여서 표시
            f"Bot: {bot_name}\n"
            f"Plan: {plan_type}\n"
            f"Payment Date: {payment_date}\n"
            f"Expire Date: {expire_date}\n"
            f"Amount: ${amount}"
        )
        # ADMIN_USER_ID로 알림 전송 (bot 변수는 app_info에서 가져온 bot 사용)
        await bot.send_message(ADMIN_USER_ID, admin_text)

    except Exception as e:
        logger.error(f"Payment handling failed for {user_id} ({bot_name}): {e}")
