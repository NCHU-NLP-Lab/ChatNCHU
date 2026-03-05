<script>
	import { toast } from 'svelte-sonner';

	import { onMount, getContext, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { getBackendConfig } from '$lib/apis';
	import { ldapUserSignIn, getSessionUser, userSignIn, userSignUp } from '$lib/apis/auths';
	import { sendVerificationCode, forgotPassword as forgotPasswordApi } from '$lib/apis/verification';

	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';
	import { WEBUI_NAME, config, user, socket } from '$lib/stores';

	import { generateInitialsImage, canvasPixelTest } from '$lib/utils';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import OnBoarding from '$lib/components/OnBoarding.svelte';
	import LanguageSwitcher from '$lib/components/common/LanguageSwitcher.svelte';
	import ThemeSwitcher from '$lib/components/common/ThemeSwitcher.svelte';

	const i18n = getContext('i18n');

	let loaded = false;

	let mode = $config?.features.enable_ldap ? 'ldap' : 'signin';

	let name = '';
	let email = '';
	let password = '';

	let ldapUsername = '';

	// ChatNCHU: Employee ID & Verification Code
	let employeeId = '';
	let verificationCode = '';
	let codeCooldown = 0;
	let cooldownInterval = null;

	// ChatNCHU: Email domain dropdown & real-time validation
	let emailLocal = '';
	let selectedDomain = '';
	let employeeIdError = '';
	let emailLocalError = '';

	$: allowedDomains = $config?.features?.allowed_email_domains ?? [];

	function getFullEmail() {
		if (allowedDomains.length > 0) {
			return `${emailLocal}@${selectedDomain}`.toLowerCase();
		}
		return email.toLowerCase();
	}

	function validateEmployeeId() {
		if (employeeId && !/^[a-zA-Z0-9]*$/.test(employeeId)) {
			employeeIdError = $i18n.t('Only letters and numbers are allowed.');
		} else {
			employeeIdError = '';
		}
	}

	function validateEmailLocal() {
		if (emailLocal && !/^[a-zA-Z0-9]*$/.test(emailLocal)) {
			emailLocalError = $i18n.t('Only letters and numbers are allowed.');
		} else {
			emailLocalError = '';
		}
	}

	$: hasValidationError = !!(employeeIdError || emailLocalError);

	// ChatNCHU: Demo session denied modal
	let showDemoBlockedModal = false;
	let demoBlockedMessage = '';

	// ChatNCHU: Forgot password state
	let forgotPasswordMode = false;
	let fpStep = 1;
	let fpEmail = '';
	let fpCode = '';
	let fpNewPassword = '';
	let fpConfirmPassword = '';
	let fpCodeCooldown = 0;
	let fpCooldownInterval = null;

	function startCooldown(type) {
		if (type === 'signup') {
			codeCooldown = 60;
			cooldownInterval = setInterval(() => {
				codeCooldown -= 1;
				if (codeCooldown <= 0) {
					if (cooldownInterval) clearInterval(cooldownInterval);
				}
			}, 1000);
		} else {
			fpCodeCooldown = 60;
			fpCooldownInterval = setInterval(() => {
				fpCodeCooldown -= 1;
				if (fpCodeCooldown <= 0) {
					if (fpCooldownInterval) clearInterval(fpCooldownInterval);
				}
			}, 1000);
		}
	}

	async function handleSendCode() {
		try {
			const fullEmail = getFullEmail();
			await sendVerificationCode(fullEmail, 'signup');
			toast.success($i18n.t('Verification code sent to your email.'));
			startCooldown('signup');
		} catch (error) {
			toast.error($i18n.t(`${error}`));
		}
	}

	async function handleFpSendCode() {
		try {
			await sendVerificationCode(fpEmail, 'password_reset');
			toast.success($i18n.t('Verification code sent to your email.'));
			startCooldown('fp');
			fpStep = 2;
		} catch (error) {
			toast.error($i18n.t(`${error}`));
		}
	}

	async function handleFpResetPassword() {
		if (fpNewPassword !== fpConfirmPassword) {
			toast.error($i18n.t('Passwords do not match.'));
			return;
		}
		try {
			await forgotPasswordApi(fpEmail, fpCode, fpNewPassword);
			toast.success($i18n.t('Password has been reset successfully. Please sign in.'));
			forgotPasswordMode = false;
			fpStep = 1;
			fpEmail = '';
			fpCode = '';
			fpNewPassword = '';
			fpConfirmPassword = '';
			mode = 'signin';
		} catch (error) {
			toast.error($i18n.t(`${error}`));
		}
	}

	const querystringValue = (key) => {
		const querystring = window.location.search;
		const urlParams = new URLSearchParams(querystring);
		return urlParams.get(key);
	};

	const setSessionUser = async (sessionUser) => {
		if (sessionUser) {
			console.log(sessionUser);
			toast.success($i18n.t(`You're now logged in.`));
			if (sessionUser.token) {
				localStorage.token = sessionUser.token;
			}

			$socket.emit('user-join', { auth: { token: sessionUser.token } });
			await user.set(sessionUser);
			await config.set(await getBackendConfig());

			const redirectPath = querystringValue('redirect') || '/';
			goto(redirectPath);
		}
	};

	const DEMO_BLOCKED_KEYWORDS = ['already logged out today', 'demo session for today has expired', 'used all your login sessions for today'];

	const signInHandler = async () => {
		const sessionUser = await userSignIn(email, password).catch((error) => {
			const msg = `${error}`;
			if (DEMO_BLOCKED_KEYWORDS.some((kw) => msg.includes(kw))) {
				demoBlockedMessage = $i18n.t(msg);
				showDemoBlockedModal = true;
			} else {
				toast.error($i18n.t(msg));
			}
			return null;
		});

		await setSessionUser(sessionUser);
	};

	const signUpHandler = async () => {
		const fullEmail = getFullEmail();
		const sessionUser = await userSignUp(
			name,
			fullEmail,
			password,
			generateInitialsImage(name),
			employeeId || undefined,
			verificationCode || undefined
		).catch((error) => {
			toast.error($i18n.t(`${error}`));
			return null;
		});

		if (!sessionUser) return;

		// First user (onboarding/admin): auto-login as before
		if ($config?.onboarding ?? false) {
			await setSessionUser(sessionUser);
			return;
		}

		// Normal signup: show success message and redirect to login
		toast.success($i18n.t('Registration successful! Please sign in.'));
		name = '';
		email = '';
		emailLocal = '';
		password = '';
		employeeId = '';
		verificationCode = '';
		mode = 'signin';
	};

	const ldapSignInHandler = async () => {
		const sessionUser = await ldapUserSignIn(ldapUsername, password).catch((error) => {
			toast.error($i18n.t(`${error}`));
			return null;
		});
		await setSessionUser(sessionUser);
	};

	const submitHandler = async () => {
		if (forgotPasswordMode) {
			return;
		}
		if (mode === 'ldap') {
			await ldapSignInHandler();
		} else if (mode === 'signin') {
			await signInHandler();
		} else {
			await signUpHandler();
		}
	};

	const checkOauthCallback = async () => {
		if (!$page.url.hash) {
			return;
		}
		const hash = $page.url.hash.substring(1);
		if (!hash) {
			return;
		}
		const params = new URLSearchParams(hash);
		const token = params.get('token');
		if (!token) {
			return;
		}
		const sessionUser = await getSessionUser(token).catch((error) => {
			toast.error($i18n.t(`${error}`));
			return null;
		});
		if (!sessionUser) {
			return;
		}
		localStorage.token = token;
		await setSessionUser(sessionUser);
	};

	let onboarding = false;

	async function setLogoImage() {
		await tick();
		const logo = document.getElementById('logo');

		if (logo) {
			const isDarkMode = document.documentElement.classList.contains('dark');

			if (isDarkMode) {
				const darkImage = new Image();
				darkImage.src = '/static/favicon-dark.png';

				darkImage.onload = () => {
					logo.src = '/static/favicon-dark.png';
					logo.style.filter = '';
				};

				darkImage.onerror = () => {
					logo.style.filter = 'invert(1)';
				};
			}
		}
	}

	onMount(async () => {
		if ($user !== undefined) {
			const redirectPath = querystringValue('redirect') || '/';
			goto(redirectPath);
		}
		await checkOauthCallback();

		loaded = true;
		setLogoImage();

		// ChatNCHU: Initialize domain dropdown
		const domains = $config?.features?.allowed_email_domains ?? [];
		if (domains.length > 0) {
			selectedDomain = domains[0];
		}

		if (($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false) {
			await signInHandler();
		} else {
			onboarding = $config?.onboarding ?? false;
		}
	});
</script>

<svelte:head>
	<title>
		{`${$WEBUI_NAME}`}
	</title>
</svelte:head>

<OnBoarding
	bind:show={onboarding}
	getStartedHandler={() => {
		onboarding = false;
		mode = $config?.features.enable_ldap ? 'ldap' : 'signup';
	}}
/>

<div id="auth-page" class="w-full h-screen max-h-[100dvh] text-white relative">
	<div class="w-full h-full absolute top-0 left-0 bg-white dark:bg-black"></div>

	<div class="w-full absolute top-0 left-0 right-0 h-8 drag-region" />

	{#if loaded}
		<div class="fixed top-4 right-4 z-[60] flex items-center gap-2">
			<ThemeSwitcher />
			<LanguageSwitcher />
		</div>

		<div
			class="fixed bg-transparent min-h-screen w-full flex justify-center font-primary z-50 text-black dark:text-white"
		>
			<div class="w-full sm:max-w-lg px-10 min-h-screen flex flex-col text-center">
				{#if ($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false}
					<div class=" my-auto pb-10 w-full">
						<div
							class="flex items-center justify-center gap-3 text-xl sm:text-2xl text-center font-semibold dark:text-gray-200"
						>
							<div>
								{$i18n.t('Signing in to {{WEBUI_NAME}}', { WEBUI_NAME: $WEBUI_NAME })}
							</div>

							<div>
								<Spinner />
							</div>
						</div>
					</div>
				{:else}
					<!-- Fixed logo at top -->
					<div class="flex-shrink-0 flex justify-center pt-8 pb-2">
						<img
							id="logo"
							crossorigin="anonymous"
							src="{WEBUI_BASE_URL}/static/splash.png"
							class="w-60 mt-4 rounded-2xl"
							alt="logo"
						/>
					</div>

					<!-- Scrollable form area -->
					<div class="flex-1 overflow-y-auto scrollbar-hidden pb-4 w-full dark:text-gray-100">
						<div class="min-h-full flex flex-col justify-center">
						<form
							class=" flex flex-col justify-center"
							on:submit={(e) => {
								e.preventDefault();
								submitHandler();
							}}
						>
							<div class="mb-1">
								<div class=" text-2xl font-medium">
									{#if $config?.onboarding ?? false}
										{$i18n.t(`Get started with {{WEBUI_NAME}}`, { WEBUI_NAME: $WEBUI_NAME })}
									{:else if mode === 'ldap'}
										{$i18n.t(`Sign in to {{WEBUI_NAME}} with LDAP`, { WEBUI_NAME: $WEBUI_NAME })}
									{:else if mode === 'signin'}
										{$i18n.t(`Sign in to {{WEBUI_NAME}}`, { WEBUI_NAME: $WEBUI_NAME })}
									{:else}
										{$i18n.t(`Sign up to {{WEBUI_NAME}}`, { WEBUI_NAME: $WEBUI_NAME })}
									{/if}
								</div>

								{#if $config?.onboarding ?? false}
									<div class=" mt-1 text-xs font-medium text-gray-500">
										ⓘ {$WEBUI_NAME}
										{$i18n.t(
											'does not make any external connections, and your data stays securely on your locally hosted server.'
										)}
									</div>
								{/if}
							</div>

							{#if $config?.features.enable_login_form || $config?.features.enable_ldap}
								<div class="flex flex-col mt-4">
									{#if mode === 'ldap'}
										<div class="mb-2">
											<div class=" text-sm font-medium text-left mb-1">{$i18n.t('Username')}</div>
											<input
												bind:value={ldapUsername}
												type="text"
												class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder-gray-400 dark:placeholder-gray-500"
												autocomplete="username"
												name="username"
												placeholder={$i18n.t('Enter Your Username')}
												required
											/>
										</div>
									{:else if mode === 'signin'}
										<!-- ChatNCHU: Login accepts email or employee ID -->
										<div class="mb-2">
											<div class=" text-sm font-medium text-left mb-1">{$i18n.t('Email or Employee ID / Student ID')}</div>
											<input
												bind:value={email}
												type="text"
												class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder-gray-400 dark:placeholder-gray-500"
												autocomplete="email"
												name="email"
												placeholder={$i18n.t('Enter Your Email or Student ID')}
												required
											/>
										</div>
									{:else}
										<!-- ChatNCHU: Signup field order: Employee ID -> Name -> Email -> Password -> Verification Code -->
										
										<!-- 1. Employee ID / Student ID -->
											<div class="mb-2">
												<div class=" text-sm font-medium text-left mb-1">{$i18n.t('Employee ID / Student ID')}</div>
												<input
													bind:value={employeeId}
													type="text"
													class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder-gray-400 dark:placeholder-gray-500"
													placeholder={$i18n.t('Enter Your Employee ID or Student ID')}
													on:input={validateEmployeeId}
													required
												/>
												{#if employeeIdError}
													<div class="text-xs text-red-500 text-left mt-0.5">{employeeIdError}</div>
												{/if}
											</div>
										
										<!-- 2. Name -->
										<div class="mb-2">
											<div class=" text-sm font-medium text-left mb-1">{$i18n.t('Full Name')}</div>
											<input
												bind:value={name}
												type="text"
												class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder-gray-400 dark:placeholder-gray-500"
												autocomplete="name"
												placeholder={$i18n.t('Enter Your Full Name')}
												required
											/>
										</div>
										
										<!-- 3. Email (with domain dropdown if whitelist configured) -->
										<div class="mb-2">
											<div class=" text-sm font-medium text-left mb-1">{$i18n.t('Email')}</div>
											{#if allowedDomains.length > 0}
												<div class="flex items-center gap-1">
													<input
														bind:value={emailLocal}
														type="text"
														class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder-gray-400 dark:placeholder-gray-500"
														placeholder={$i18n.t('Username')}
														on:input={validateEmailLocal}
														required
													/>
													<span class="text-sm text-gray-500 shrink-0">@</span>
													<select
														bind:value={selectedDomain}
														class="my-0.5 text-sm outline-hidden bg-transparent dark:bg-gray-900 dark:text-gray-200"
													>
														{#each allowedDomains as domain}
															<option value={domain}>{domain}</option>
														{/each}
													</select>
												</div>
												{#if emailLocalError}
													<div class="text-xs text-red-500 text-left mt-0.5">{emailLocalError}</div>
												{/if}
											{:else}
												<input
													bind:value={email}
													type="email"
													class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder-gray-400 dark:placeholder-gray-500"
													autocomplete="email"
													name="email"
													placeholder={$i18n.t('Enter Your Email')}
													required
												/>
											{/if}
										</div>
									{/if}
									
									{#if mode !== 'ldap'}
										<div>
											<div class=" text-sm font-medium text-left mb-1">{$i18n.t('Password')}</div>
											
											<input
												bind:value={password}
												type="password"
												class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder-gray-400 dark:placeholder-gray-500"
												placeholder={$i18n.t('Enter Your Password')}
												autocomplete="current-password"
												name="current-password"
												required
											/>
										</div>
									{/if}
									
									{#if mode === 'signup' && $config?.features?.enable_email_verification && !($config?.onboarding ?? false)}
										<div class="mt-2">
											<div class=" text-sm font-medium text-left mb-1">{$i18n.t('Verification Code')}</div>
											<div class="flex gap-2 items-center">
												<input
													bind:value={verificationCode}
													type="text"
													maxlength="6"
													class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder-gray-400 dark:placeholder-gray-500"
													placeholder={$i18n.t('Enter 6-digit code')}
													required
												/>
												<button
													type="button"
													class="shrink-0 text-xs px-3 py-1.5 rounded-full font-medium transition
														{codeCooldown > 0
															? 'bg-gray-300 dark:bg-gray-600 cursor-not-allowed'
															: 'bg-gray-700/10 hover:bg-gray-700/20 dark:bg-gray-100/10 dark:hover:bg-gray-100/20'}"
													disabled={codeCooldown > 0 || (allowedDomains.length > 0 ? !emailLocal : !email)}
													on:click={handleSendCode}
												>
													{codeCooldown > 0 ? `${codeCooldown}s` : $i18n.t('Send Code')}
												</button>
											</div>
										</div>
									{/if}
								</div>
							{/if}
							<div class="mt-5">
								{#if $config?.features.enable_login_form || $config?.features.enable_ldap}
									{#if mode === 'ldap'}
										<button
											class="bg-gray-700/20 hover:bg-gray-700/30 dark:bg-gray-100/20 dark:hover:bg-gray-100/30 dark:text-gray-100 transition w-full rounded-full font-medium text-sm py-2.5"
											type="submit"
										>
											{$i18n.t('Authenticate')}
										</button>
									{:else}
										<button
											class="bg-gray-700/20 hover:bg-gray-700/30 dark:bg-gray-100/20 dark:hover:bg-gray-100/30 dark:text-gray-100 transition w-full rounded-full font-medium text-sm py-2.5"
											type="submit"
											disabled={hasValidationError}
										>
											{mode === 'signin'
												? $i18n.t('Sign in')
												: ($config?.onboarding ?? false)
													? $i18n.t('Create Admin Account')
													: $i18n.t('Create Account')}
										</button>

										{#if $config?.features.enable_signup && !($config?.onboarding ?? false)}
											<div class=" mt-4 text-sm text-center">
												{mode === 'signin'
													? $i18n.t("Don't have an account?")
													: $i18n.t('Already have an account?')}

												<button
													class=" font-medium underline"
													type="button"
													on:click={() => {
														if (mode === 'signin') {
															mode = 'signup';
														} else {
															mode = 'signin';
														}
													}}
												>
													{mode === 'signin' ? $i18n.t('Sign up') : $i18n.t('Sign in')}
												</button>
											</div>
										{/if}

										{#if mode === 'signin' && $config?.features?.enable_email_verification}
											<div class="mt-2 text-sm text-center">
												<button
													class="font-medium underline text-gray-500 dark:text-gray-400"
													type="button"
													on:click={() => {
														forgotPasswordMode = true;
														fpStep = 1;
													}}
												>
													{$i18n.t('Forgot password?')}
												</button>
											</div>
										{/if}
									{/if}
								{/if}
							</div>
						</form>

						{#if forgotPasswordMode}
							<div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/50">
								<div class="bg-white dark:bg-gray-900 rounded-2xl p-6 w-full max-w-sm mx-4 shadow-xl">
									<h3 class="text-lg font-medium mb-4 text-black dark:text-white">
										{$i18n.t('Reset Password')}
									</h3>

									{#if fpStep === 1}
										<div class="space-y-3">
											<div>
												<div class="text-sm font-medium text-left mb-1 text-gray-700 dark:text-gray-300">{$i18n.t('Email')}</div>
												<input
													bind:value={fpEmail}
													type="email"
													class="w-full text-sm border rounded-lg px-3 py-2 bg-transparent dark:border-gray-600 text-black dark:text-white"
													placeholder={$i18n.t('Enter Your Email')}
													required
												/>
											</div>
											<button
												class="w-full bg-gray-700/10 hover:bg-gray-700/20 dark:bg-gray-100/10 dark:hover:bg-gray-100/20 rounded-full py-2 text-sm font-medium text-black dark:text-white"
												on:click={handleFpSendCode}
												disabled={!fpEmail}
											>
												{$i18n.t('Send Verification Code')}
											</button>
										</div>
									{:else if fpStep === 2}
										<div class="space-y-3">
											<p class="text-sm text-gray-500 dark:text-gray-400">
												{$i18n.t('A verification code has been sent to')} {fpEmail}
											</p>
											<div>
												<div class="text-sm font-medium text-left mb-1 text-gray-700 dark:text-gray-300">{$i18n.t('Verification Code')}</div>
												<input
													bind:value={fpCode}
													type="text"
													maxlength="6"
													class="w-full text-sm border rounded-lg px-3 py-2 bg-transparent dark:border-gray-600 text-black dark:text-white"
													placeholder={$i18n.t('Enter 6-digit code')}
													required
												/>
											</div>
											<button
												class="w-full bg-gray-700/10 hover:bg-gray-700/20 dark:bg-gray-100/10 dark:hover:bg-gray-100/20 rounded-full py-2 text-sm font-medium text-black dark:text-white"
												on:click={() => { fpStep = 3; }}
												disabled={!fpCode || fpCode.length < 6}
											>
												{$i18n.t('Next')}
											</button>
											<button
												type="button"
												class="w-full text-xs text-center underline text-gray-500 dark:text-gray-400"
												disabled={fpCodeCooldown > 0}
												on:click={handleFpSendCode}
											>
												{fpCodeCooldown > 0 ? `${$i18n.t('Resend in')} ${fpCodeCooldown}s` : $i18n.t('Resend Code')}
											</button>
										</div>
									{:else if fpStep === 3}
										<div class="space-y-3">
											<div>
												<div class="text-sm font-medium text-left mb-1 text-gray-700 dark:text-gray-300">{$i18n.t('New Password')}</div>
												<input
													bind:value={fpNewPassword}
													type="password"
													class="w-full text-sm border rounded-lg px-3 py-2 bg-transparent dark:border-gray-600 text-black dark:text-white"
													placeholder={$i18n.t('Enter New Password')}
													required
												/>
											</div>
											<div>
												<div class="text-sm font-medium text-left mb-1 text-gray-700 dark:text-gray-300">{$i18n.t('Confirm Password')}</div>
												<input
													bind:value={fpConfirmPassword}
													type="password"
													class="w-full text-sm border rounded-lg px-3 py-2 bg-transparent dark:border-gray-600 text-black dark:text-white"
													placeholder={$i18n.t('Confirm New Password')}
													required
												/>
											</div>
											<button
												class="w-full bg-gray-700/10 hover:bg-gray-700/20 dark:bg-gray-100/10 dark:hover:bg-gray-100/20 rounded-full py-2 text-sm font-medium text-black dark:text-white"
												on:click={handleFpResetPassword}
												disabled={!fpNewPassword || !fpConfirmPassword}
											>
												{$i18n.t('Reset Password')}
											</button>
										</div>
									{/if}

									<button
										class="mt-4 w-full text-sm text-center text-gray-500 dark:text-gray-400 underline"
										on:click={() => {
											forgotPasswordMode = false;
											fpStep = 1;
										}}
									>
										{$i18n.t('Cancel')}
									</button>
								</div>
							</div>
						{/if}

						{#if showDemoBlockedModal}
							<div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/50">
								<div class="bg-white dark:bg-gray-900 border border-red-300 dark:border-red-700 rounded-2xl p-6 w-full max-w-sm mx-4 shadow-xl text-center">
									<div class="flex justify-center mb-4">
										<svg xmlns="http://www.w3.org/2000/svg" class="size-12 text-red-500" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
											<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
										</svg>
									</div>
									<h3 class="text-lg font-semibold mb-2 text-red-600 dark:text-red-400">
										{$i18n.t('Session Unavailable')}
									</h3>
									<p class="text-sm text-gray-600 dark:text-gray-300 mb-6 leading-relaxed">
										{demoBlockedMessage}
									</p>
									<button
										class="w-full bg-red-600 hover:bg-red-700 rounded-full py-2.5 text-sm font-medium text-white transition"
										on:click={() => { showDemoBlockedModal = false; }}
									>
										{$i18n.t('OK')}
									</button>
								</div>
							</div>
						{/if}

						{#if Object.keys($config?.oauth?.providers ?? {}).length > 0}
							<div class="inline-flex items-center justify-center w-full">
								<hr class="w-32 h-px my-4 border-0 dark:bg-gray-100/10 bg-gray-700/10" />
								{#if $config?.features.enable_login_form || $config?.features.enable_ldap}
									<span
										class="px-3 text-sm font-medium text-gray-900 dark:text-white bg-transparent"
										>{$i18n.t('or')}</span
									>
								{/if}

								<hr class="w-32 h-px my-4 border-0 dark:bg-gray-100/10 bg-gray-700/10" />
							</div>
							<div class="flex flex-col space-y-2">
								{#if $config?.oauth?.providers?.google}
									<button
										class="flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
										on:click={() => {
											window.location.href = `${WEBUI_BASE_URL}/oauth/google/login`;
										}}
									>
										<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" class="size-6 mr-3">
											<path
												fill="#EA4335"
												d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
											/><path
												fill="#4285F4"
												d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
											/><path
												fill="#FBBC05"
												d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
											/><path
												fill="#34A853"
												d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
											/><path fill="none" d="M0 0h48v48H0z" />
										</svg>
										<span>{$i18n.t('Continue with {{provider}}', { provider: 'Google' })}</span>
									</button>
								{/if}
								{#if $config?.oauth?.providers?.microsoft}
									<button
										class="flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
										on:click={() => {
											window.location.href = `${WEBUI_BASE_URL}/oauth/microsoft/login`;
										}}
									>
										<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 21 21" class="size-6 mr-3">
											<rect x="1" y="1" width="9" height="9" fill="#f25022" /><rect
												x="1"
												y="11"
												width="9"
												height="9"
												fill="#00a4ef"
											/><rect x="11" y="1" width="9" height="9" fill="#7fba00" /><rect
												x="11"
												y="11"
												width="9"
												height="9"
												fill="#ffb900"
											/>
										</svg>
										<span>{$i18n.t('Continue with {{provider}}', { provider: 'Microsoft' })}</span>
									</button>
								{/if}
								{#if $config?.oauth?.providers?.github}
									<button
										class="flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
										on:click={() => {
											window.location.href = `${WEBUI_BASE_URL}/oauth/github/login`;
										}}
									>
										<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-6 mr-3">
											<path
												fill="currentColor"
												d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.92 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57C20.565 21.795 24 17.31 24 12c0-6.63-5.37-12-12-12z"
											/>
										</svg>
										<span>{$i18n.t('Continue with {{provider}}', { provider: 'GitHub' })}</span>
									</button>
								{/if}
								{#if $config?.oauth?.providers?.oidc}
									<button
										class="flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
										on:click={() => {
											window.location.href = `${WEBUI_BASE_URL}/oauth/oidc/login`;
										}}
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											fill="none"
											viewBox="0 0 24 24"
											stroke-width="1.5"
											stroke="currentColor"
											class="size-6 mr-3"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												d="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1 1 21.75 8.25Z"
											/>
										</svg>

										<span
											>{$i18n.t('Continue with {{provider}}', {
												provider: $config?.oauth?.providers?.oidc ?? 'SSO'
											})}</span
										>
									</button>
								{/if}
							</div>
						{/if}

						{#if $config?.features.enable_ldap && $config?.features.enable_login_form}
							<div class="mt-2">
								<button
									class="flex justify-center items-center text-xs w-full text-center underline"
									type="button"
									on:click={() => {
										if (mode === 'ldap')
											mode = ($config?.onboarding ?? false) ? 'signup' : 'signin';
										else mode = 'ldap';
									}}
								>
									<span
										>{mode === 'ldap'
											? $i18n.t('Continue with Email')
											: $i18n.t('Continue with LDAP')}</span
									>
								</button>
							</div>
						{/if}

						</div>
					</div>

					<!-- Fixed footer at bottom -->
					<div class="flex-shrink-0 pb-4 pt-2 text-xs text-black/70 dark:text-white/70 text-center leading-relaxed">
						<div>© Maintained by <a href="https://nlpnchu.org/" target="_blank" rel="noopener" class="hover:underline">NCHU NLP Lab</a></div>
						<div>
							{$i18n.t('Technical issues')}: <a href="mailto:nlpnchu@gmail.com" class="hover:underline">nlpnchu@gmail.com</a>
							{#if $config?.admin_email}
								<span class="mx-1">|</span>
								{$i18n.t('Account issues')}: <a href="mailto:{$config.admin_email}" class="hover:underline">{$config.admin_email}</a>
							{/if}
						</div>
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>
