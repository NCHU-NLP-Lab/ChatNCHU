<script lang="ts">
	import DOMPurify from 'dompurify';

	import { getBackendConfig, getVersionUpdates, getWebhookUrl, updateWebhookUrl } from '$lib/apis';
	import {
		getAdminConfig,
		getLdapConfig,
		getLdapServer,
		updateAdminConfig,
		updateLdapConfig,
		updateLdapServer
	} from '$lib/apis/auths';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { WEBUI_BUILD_HASH, WEBUI_VERSION } from '$lib/constants';
	import { config, showChangelog, user } from '$lib/stores';
	import { compareVersion } from '$lib/utils';
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	const i18n = getContext('i18n');

	export let saveHandler: Function;

	let updateAvailable = null;
	let version = {
		current: '',
		latest: ''
	};

	let adminConfig = null;
	let webhookUrl = '';

	// LDAP
	let ENABLE_LDAP = false;
	let LDAP_SERVER = {
		label: '',
		host: '',
		port: '',
		attribute_for_mail: 'mail',
		attribute_for_username: 'uid',
		app_dn: '',
		app_dn_password: '',
		search_base: '',
		search_filters: '',
		use_tls: false,
		certificate_path: '',
		ciphers: ''
	};

	// ChatNCHU: Allowed Email Domains list
	let emailDomains: { domain: string; enabled: boolean }[] = [];
	let editingDomainIndex: number | null = null;
	let editingDomainValue = '';
	let newDomainValue = '';
	let showAddDomain = false;

	function parseDomainConfig(raw: string): { domain: string; enabled: boolean }[] {
		if (!raw || !raw.trim()) return [];
		const trimmed = raw.trim();
		if (trimmed.startsWith('[')) {
			try {
				return JSON.parse(trimmed);
			} catch {
				return [];
			}
		}
		return trimmed.split(',').filter((d) => d.trim()).map((d) => ({ domain: d.trim(), enabled: true }));
	}

	function serializeDomainConfig(domains: { domain: string; enabled: boolean }[]): string {
		if (domains.length === 0) return '';
		return JSON.stringify(domains);
	}

	function syncDomainsToConfig() {
		if (adminConfig) {
			adminConfig.ALLOWED_EMAIL_DOMAINS = serializeDomainConfig(emailDomains);
		}
	}

	const checkForVersionUpdates = async () => {
		updateAvailable = null;
		version = await getVersionUpdates(localStorage.token).catch((error) => {
			return {
				current: WEBUI_VERSION,
				latest: WEBUI_VERSION
			};
		});

		console.log(version);

		updateAvailable = compareVersion(version.latest, version.current);
		console.log(updateAvailable);
	};

	const updateLdapServerHandler = async () => {
		if (!ENABLE_LDAP) return;
		const res = await updateLdapServer(localStorage.token, LDAP_SERVER).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (res) {
			toast.success($i18n.t('LDAP server updated'));
		}
	};

	const updateHandler = async () => {
		webhookUrl = await updateWebhookUrl(localStorage.token, webhookUrl);
		const res = await updateAdminConfig(localStorage.token, adminConfig);
		await updateLdapServerHandler();

		if (res) {
			saveHandler();
		} else {
			toast.error(i18n.t('Failed to update settings'));
		}
	};

	onMount(async () => {
		checkForVersionUpdates();

		await Promise.all([
			(async () => {
				adminConfig = await getAdminConfig(localStorage.token);
				emailDomains = parseDomainConfig(adminConfig?.ALLOWED_EMAIL_DOMAINS ?? '');
			})(),

			(async () => {
				webhookUrl = await getWebhookUrl(localStorage.token);
			})(),
			(async () => {
				LDAP_SERVER = await getLdapServer(localStorage.token);
			})()
		]);

		const ldapConfig = await getLdapConfig(localStorage.token);
		ENABLE_LDAP = ldapConfig.ENABLE_LDAP;
	});
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	on:submit|preventDefault={async () => {
		updateHandler();
	}}
>
	<div class="mt-0.5 space-y-3 overflow-y-scroll scrollbar-hidden h-full">
		{#if adminConfig !== null}
			<div class="">
				<div class="mb-3.5">
					<div class=" mb-2.5 text-base font-medium">{$i18n.t('General')}</div>

					<hr class=" border-gray-100 dark:border-gray-850 my-2" />

					<div class="mb-2.5">
						<div class=" mb-1 text-xs font-medium flex space-x-2 items-center">
							<div>
								{$i18n.t('Version')}
							</div>
						</div>
						<div class="flex w-full justify-between items-center">
							<div class="flex flex-col text-xs text-gray-700 dark:text-gray-200">
								<div>
									ChatNCHU v{WEBUI_VERSION} (based on Open WebUI v0.6.5)
								</div>
							</div>
						</div>
					</div>

					<div class="mb-2.5">
						<div class="flex w-full justify-between items-center">
							<div class="text-xs pr-2">
								<div class="">
									{$i18n.t('License')}
								</div>
								<div class="text-xs text-gray-500">
									AGPL-3.0 (Base: Open WebUI BSD-3-Clause)
								</div>
							</div>

							<a
								class="flex-shrink-0 text-xs font-medium underline"
								href="https://github.com/NCHU-NLP-Lab/ChatNCHU"
								target="_blank"
							>
								GitHub
							</a>
						</div>
					</div>
				</div>

				<div class="mb-3">
					<div class=" mb-2.5 text-base font-medium">{$i18n.t('Authentication')}</div>

					<hr class=" border-gray-100 dark:border-gray-850 my-2" />

					<div class="  mb-2.5 flex w-full justify-between">
						<div class=" self-center text-xs font-medium">{$i18n.t('Default User Role')}</div>
						<div class="flex items-center relative">
							<select
								class="dark:bg-gray-900 w-fit pr-8 rounded-sm px-2 text-xs bg-transparent outline-hidden text-right"
								bind:value={adminConfig.DEFAULT_USER_ROLE}
								placeholder="Select a role"
							>
								<option value="pending">{$i18n.t('pending')}</option>
								<option value="user">{$i18n.t('user')}</option>
							</select>
						</div>
					</div>

					<div class=" mb-2.5 flex w-full justify-between pr-2">
						<div class=" self-center text-xs font-medium">{$i18n.t('Enable New Sign Ups')}</div>

						<Switch bind:state={adminConfig.ENABLE_SIGNUP} />
					</div>

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('Show Admin Details in Account Pending Overlay')}
						</div>

						<Switch bind:state={adminConfig.SHOW_ADMIN_DETAILS} />
					</div>

					{#if $user?.role === 'super_admin'}
					<div class="mb-2.5 flex w-full justify-between pr-2">
						<div class=" self-center text-xs font-medium">{$i18n.t('Enable API Key')}</div>

						<Switch bind:state={adminConfig.ENABLE_API_KEY} />
					</div>

					{#if adminConfig?.ENABLE_API_KEY}
						<div class="mb-2.5 flex w-full justify-between pr-2">
							<div class=" self-center text-xs font-medium">
								{$i18n.t('API Key Endpoint Restrictions')}
							</div>

							<Switch bind:state={adminConfig.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS} />
						</div>

						{#if adminConfig?.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS}
							<div class=" flex w-full flex-col pr-2">
								<div class=" text-xs font-medium">
									{$i18n.t('Allowed Endpoints')}
								</div>

								<input
									class="w-full mt-1 rounded-lg text-sm dark:text-gray-300 bg-transparent outline-hidden"
									type="text"
									placeholder={`e.g.) /api/v1/messages, /api/v1/channels`}
									bind:value={adminConfig.API_KEY_ALLOWED_ENDPOINTS}
								/>

								<div class="mt-2 text-xs text-gray-400 dark:text-gray-500">
									<!-- https://docs.openwebui.com/getting-started/advanced-topics/api-endpoints -->
									<a
										href="https://docs.openwebui.com/getting-started/api-endpoints"
										target="_blank"
										class=" text-gray-300 font-medium underline"
									>
										{$i18n.t('To learn more about available endpoints, visit our documentation.')}
									</a>
								</div>
							</div>
						{/if}
					{/if}

					<div class=" mb-2.5 w-full justify-between">
						<div class="flex w-full justify-between">
							<div class=" self-center text-xs font-medium">{$i18n.t('JWT Expiration')}</div>
						</div>

						<div class="flex mt-2 space-x-2">
							<input
								class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
								type="text"
								placeholder={`e.g.) "30m","1h", "10d". `}
								bind:value={adminConfig.JWT_EXPIRES_IN}
							/>
						</div>

						<div class="mt-2 text-xs text-gray-400 dark:text-gray-500">
							{$i18n.t('Valid time units:')}
							<span class=" text-gray-300 font-medium"
								>{$i18n.t("'s', 'm', 'h', 'd', 'w' or '-1' for no expiration.")}</span
							>
						</div>
					</div>

					<div class=" space-y-3">
						<div class="mt-2 space-y-2 pr-1.5">
							<div class="flex justify-between items-center text-sm">
								<div class="  font-medium">{$i18n.t('LDAP')}</div>

								<div class="mt-1">
									<Switch
										bind:state={ENABLE_LDAP}
										on:change={async () => {
											updateLdapConfig(localStorage.token, ENABLE_LDAP);
										}}
									/>
								</div>
							</div>

							{#if ENABLE_LDAP}
								<div class="flex flex-col gap-1">
									<div class="flex w-full gap-2">
										<div class="w-full">
											<div class=" self-center text-xs font-medium min-w-fit mb-1">
												{$i18n.t('Label')}
											</div>
											<input
												class="w-full bg-transparent outline-hidden py-0.5"
												required
												placeholder={$i18n.t('Enter server label')}
												bind:value={LDAP_SERVER.label}
											/>
										</div>
										<div class="w-full"></div>
									</div>
									<div class="flex w-full gap-2">
										<div class="w-full">
											<div class=" self-center text-xs font-medium min-w-fit mb-1">
												{$i18n.t('Host')}
											</div>
											<input
												class="w-full bg-transparent outline-hidden py-0.5"
												required
												placeholder={$i18n.t('Enter server host')}
												bind:value={LDAP_SERVER.host}
											/>
										</div>
										<div class="w-full">
											<div class=" self-center text-xs font-medium min-w-fit mb-1">
												{$i18n.t('Port')}
											</div>
											<Tooltip
												placement="top-start"
												content={$i18n.t('Default to 389 or 636 if TLS is enabled')}
												className="w-full"
											>
												<input
													class="w-full bg-transparent outline-hidden py-0.5"
													type="number"
													placeholder={$i18n.t('Enter server port')}
													bind:value={LDAP_SERVER.port}
												/>
											</Tooltip>
										</div>
									</div>
									<div class="flex w-full gap-2">
										<div class="w-full">
											<div class=" self-center text-xs font-medium min-w-fit mb-1">
												{$i18n.t('Application DN')}
											</div>
											<Tooltip
												content={$i18n.t('The Application Account DN you bind with for search')}
												placement="top-start"
											>
												<input
													class="w-full bg-transparent outline-hidden py-0.5"
													required
													placeholder={$i18n.t('Enter Application DN')}
													bind:value={LDAP_SERVER.app_dn}
												/>
											</Tooltip>
										</div>
										<div class="w-full">
											<div class=" self-center text-xs font-medium min-w-fit mb-1">
												{$i18n.t('Application DN Password')}
											</div>
											<SensitiveInput
												placeholder={$i18n.t('Enter Application DN Password')}
												bind:value={LDAP_SERVER.app_dn_password}
											/>
										</div>
									</div>
									<div class="flex w-full gap-2">
										<div class="w-full">
											<div class=" self-center text-xs font-medium min-w-fit mb-1">
												{$i18n.t('Attribute for Mail')}
											</div>
											<Tooltip
												content={$i18n.t(
													'The LDAP attribute that maps to the mail that users use to sign in.'
												)}
												placement="top-start"
											>
												<input
													class="w-full bg-transparent outline-hidden py-0.5"
													required
													placeholder={$i18n.t('Example: mail')}
													bind:value={LDAP_SERVER.attribute_for_mail}
												/>
											</Tooltip>
										</div>
									</div>
									<div class="flex w-full gap-2">
										<div class="w-full">
											<div class=" self-center text-xs font-medium min-w-fit mb-1">
												{$i18n.t('Attribute for Username')}
											</div>
											<Tooltip
												content={$i18n.t(
													'The LDAP attribute that maps to the username that users use to sign in.'
												)}
												placement="top-start"
											>
												<input
													class="w-full bg-transparent outline-hidden py-0.5"
													required
													placeholder={$i18n.t(
														'Example: sAMAccountName or uid or userPrincipalName'
													)}
													bind:value={LDAP_SERVER.attribute_for_username}
												/>
											</Tooltip>
										</div>
									</div>
									<div class="flex w-full gap-2">
										<div class="w-full">
											<div class=" self-center text-xs font-medium min-w-fit mb-1">
												{$i18n.t('Search Base')}
											</div>
											<Tooltip
												content={$i18n.t('The base to search for users')}
												placement="top-start"
											>
												<input
													class="w-full bg-transparent outline-hidden py-0.5"
													required
													placeholder={$i18n.t('Example: ou=users,dc=foo,dc=example')}
													bind:value={LDAP_SERVER.search_base}
												/>
											</Tooltip>
										</div>
									</div>
									<div class="flex w-full gap-2">
										<div class="w-full">
											<div class=" self-center text-xs font-medium min-w-fit mb-1">
												{$i18n.t('Search Filters')}
											</div>
											<input
												class="w-full bg-transparent outline-hidden py-0.5"
												placeholder={$i18n.t('Example: (&(objectClass=inetOrgPerson)(uid=%s))')}
												bind:value={LDAP_SERVER.search_filters}
											/>
										</div>
									</div>
									<div class="text-xs text-gray-400 dark:text-gray-500">
										<a
											class=" text-gray-300 font-medium underline"
											href="https://ldap.com/ldap-filters/"
											target="_blank"
										>
											{$i18n.t('Click here for filter guides.')}
										</a>
									</div>
									<div>
										<div class="flex justify-between items-center text-sm">
											<div class="  font-medium">{$i18n.t('TLS')}</div>

											<div class="mt-1">
												<Switch bind:state={LDAP_SERVER.use_tls} />
											</div>
										</div>
										{#if LDAP_SERVER.use_tls}
											<div class="flex w-full gap-2">
												<div class="w-full">
													<div class=" self-center text-xs font-medium min-w-fit mb-1 mt-1">
														{$i18n.t('Certificate Path')}
													</div>
													<input
														class="w-full bg-transparent outline-hidden py-0.5"
														placeholder={$i18n.t('Enter certificate path')}
														bind:value={LDAP_SERVER.certificate_path}
													/>
												</div>
											</div>
											<div class="flex w-full gap-2">
												<div class="w-full">
													<div class=" self-center text-xs font-medium min-w-fit mb-1">
														{$i18n.t('Ciphers')}
													</div>
													<Tooltip content={$i18n.t('Default to ALL')} placement="top-start">
														<input
															class="w-full bg-transparent outline-hidden py-0.5"
															placeholder={$i18n.t('Example: ALL')}
															bind:value={LDAP_SERVER.ciphers}
														/>
													</Tooltip>
												</div>
												<div class="w-full"></div>
											</div>
										{/if}
									</div>
								</div>
							{/if}
						</div>
					</div>
					{/if}
				</div>

				<div class="mb-3">
					<div class=" mb-2.5 text-base font-medium">{$i18n.t('ChatNCHU Settings')}</div>

					<hr class=" border-gray-100 dark:border-gray-850 my-2" />

					<div class="mb-2.5">
						<div class="flex items-center justify-between mb-1">
							<div class="text-xs font-medium">{$i18n.t('Allowed Email Domains')}</div>
							<Tooltip content={$i18n.t('Add Domain')}>
								<button
									class="p-0.5 bg-transparent hover:bg-gray-100 dark:hover:bg-gray-850 rounded-lg transition"
									type="button"
									on:click={() => { showAddDomain = true; newDomainValue = ''; }}
								>
									<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5">
										<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
									</svg>
								</button>
							</Tooltip>
						</div>

						{#if emailDomains.length === 0 && !showAddDomain}
							<div class="text-xs text-gray-400 dark:text-gray-500 py-2">{$i18n.t('No domain restrictions. All email domains are allowed.')}</div>
						{/if}

						<div class="flex flex-col gap-1.5">
							{#each emailDomains as entry, idx}
								<div class="flex items-center gap-2 rounded-lg py-1.5 px-3 bg-gray-50 dark:bg-gray-850">
									{#if editingDomainIndex === idx}
										<input
											class="flex-1 text-sm bg-transparent outline-none"
											type="text"
											bind:value={editingDomainValue}
											on:keydown={(e) => {
												if (e.key === 'Enter') {
													e.preventDefault();
													if (editingDomainValue.trim()) {
														emailDomains[idx].domain = editingDomainValue.trim();
														syncDomainsToConfig();
													}
													editingDomainIndex = null;
												} else if (e.key === 'Escape') {
													editingDomainIndex = null;
												}
											}}
											autofocus
										/>
										<button
											class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition"
											type="button"
											on:click={() => {
												if (editingDomainValue.trim()) {
													emailDomains[idx].domain = editingDomainValue.trim();
													syncDomainsToConfig();
												}
												editingDomainIndex = null;
											}}
										>
											<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5 text-green-600">
												<path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5" />
											</svg>
										</button>
									{:else}
										<div class="flex-1 text-sm {entry.enabled ? '' : 'line-through text-gray-400 dark:text-gray-500'}">
											@{entry.domain}
										</div>
										<Tooltip content={$i18n.t('Edit')}>
											<button
												class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition"
												type="button"
												on:click={() => { editingDomainIndex = idx; editingDomainValue = entry.domain; }}
											>
												<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3">
													<path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Z" />
												</svg>
											</button>
										</Tooltip>
										<Tooltip content={entry.enabled ? $i18n.t('Enabled') : $i18n.t('Disabled')}>
											<Switch
												bind:state={entry.enabled}
												on:change={() => { syncDomainsToConfig(); }}
											/>
										</Tooltip>
										<Tooltip content={$i18n.t('Delete')}>
											<button
												class="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition"
												type="button"
												on:click={() => { emailDomains = emailDomains.filter((_, i) => i !== idx); syncDomainsToConfig(); }}
											>
												<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3 text-red-500">
													<path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
												</svg>
											</button>
										</Tooltip>
									{/if}
								</div>
							{/each}

							{#if showAddDomain}
								<div class="flex items-center gap-2 rounded-lg py-1.5 px-3 bg-gray-50 dark:bg-gray-850 border border-dashed border-gray-300 dark:border-gray-600">
									<span class="text-sm text-gray-400">@</span>
									<input
										class="flex-1 text-sm bg-transparent outline-none"
										type="text"
										placeholder="nchu.edu.tw"
										bind:value={newDomainValue}
										on:keydown={(e) => {
											if (e.key === 'Enter') {
												e.preventDefault();
												if (newDomainValue.trim()) {
													emailDomains = [...emailDomains, { domain: newDomainValue.trim(), enabled: true }];
													syncDomainsToConfig();
													newDomainValue = '';
												}
												showAddDomain = false;
											} else if (e.key === 'Escape') {
												showAddDomain = false;
											}
										}}
										autofocus
									/>
									<button
										class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition"
										type="button"
										on:click={() => {
											if (newDomainValue.trim()) {
												emailDomains = [...emailDomains, { domain: newDomainValue.trim(), enabled: true }];
												syncDomainsToConfig();
												newDomainValue = '';
											}
											showAddDomain = false;
										}}
									>
										<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5 text-green-600">
											<path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5" />
										</svg>
									</button>
									<button
										class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition"
										type="button"
										on:click={() => { showAddDomain = false; }}
									>
										<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5 text-gray-400">
											<path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
										</svg>
									</button>
								</div>
							{/if}
						</div>
					</div>


					<div class="mb-2.5">
						<div class="text-xs font-medium">{$i18n.t('Admin Email')}</div>
						<div class="text-xs text-gray-500 mb-1">{$i18n.t('Contact email shown on login page')}</div>
						<input
							class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
							type="email"
							placeholder="admin@example.com"
							bind:value={adminConfig.ADMIN_EMAIL}
						/>
					</div>

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class="self-center text-xs font-medium">
							{$i18n.t('Enable Daily Login Time Limit')}
						</div>
						<Switch bind:state={adminConfig.ENABLE_DEMO_TIME_LIMIT} />
					</div>

					{#if adminConfig.ENABLE_DEMO_TIME_LIMIT}
						<div class="mb-2.5">
							<div class="mb-1 text-xs font-medium">{$i18n.t('Daily Login Limit')}</div>
							<input
								class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850"
								type="number"
								min="1"
								bind:value={adminConfig.DEMO_DAILY_LOGIN_LIMIT}
							/>
						</div>

						<div class="mb-2.5">
							<div class="mb-1 text-xs font-medium">{$i18n.t('Session Duration (seconds)')}</div>
							<input
								class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850"
								type="number"
								min="60"
								bind:value={adminConfig.DEMO_SESSION_DURATION}
							/>
						</div>
					{/if}

					{#if $user?.role === 'super_admin'}
					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class="self-center text-xs font-medium">
							{$i18n.t('Enable Email Verification')}
						</div>
						<Switch bind:state={adminConfig.ENABLE_EMAIL_VERIFICATION} />
					</div>

					{#if adminConfig.ENABLE_EMAIL_VERIFICATION}
						<div class="mt-3 mb-1 text-xs font-semibold text-gray-500 dark:text-gray-400">{$i18n.t('SMTP Configuration')}</div>

						<div class="mb-2.5">
							<div class="mb-1 text-xs font-medium">{$i18n.t('SMTP Host')}</div>
							<input
								class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850"
								type="text"
								placeholder="smtp.gmail.com"
								bind:value={adminConfig.SMTP_HOST}
							/>
						</div>

						<div class="mb-2.5">
							<div class="mb-1 text-xs font-medium">{$i18n.t('SMTP Port')}</div>
							<input
								class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850"
								type="number"
								placeholder="587"
								bind:value={adminConfig.SMTP_PORT}
							/>
						</div>

						<div class="mb-2.5">
							<div class="mb-1 text-xs font-medium">{$i18n.t('SMTP User')}</div>
							<input
								class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850"
								type="text"
								bind:value={adminConfig.SMTP_USER}
							/>
						</div>

						<div class="mb-2.5">
							<div class="mb-1 text-xs font-medium">{$i18n.t('SMTP Password')}</div>
							<SensitiveInput
								bind:value={adminConfig.SMTP_PASSWORD}
								inputClassName="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
							/>
						</div>

						<div class="mb-2.5">
							<div class="mb-1 text-xs font-medium">{$i18n.t('SMTP From')}</div>
							<input
								class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850"
								type="text"
								placeholder="chatnchu@nchu.edu.tw"
								bind:value={adminConfig.SMTP_FROM}
							/>
						</div>

						<div class="mb-2.5 flex w-full items-center justify-between pr-2">
							<div class="self-center text-xs font-medium">
								{$i18n.t('SMTP Use TLS')}
							</div>
							<Switch bind:state={adminConfig.SMTP_USE_TLS} />
						</div>
					{/if}
					{/if}
				</div>

				{#if $user?.role === 'super_admin'}
				<div class="mb-3">
					<div class=" mb-2.5 text-base font-medium">{$i18n.t('Features')}</div>

					<hr class=" border-gray-100 dark:border-gray-850 my-2" />

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('Enable Community Sharing')}
						</div>

						<Switch bind:state={adminConfig.ENABLE_COMMUNITY_SHARING} />
					</div>

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">{$i18n.t('Enable Message Rating')}</div>

						<Switch bind:state={adminConfig.ENABLE_MESSAGE_RATING} />
					</div>

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('Channels')} ({$i18n.t('Beta')})
						</div>

						<Switch bind:state={adminConfig.ENABLE_CHANNELS} />
					</div>

					<div class="mb-2.5 flex w-full items-center justify-between pr-2">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('User Webhooks')}
						</div>

						<Switch bind:state={adminConfig.ENABLE_USER_WEBHOOKS} />
					</div>

					<div class="mb-2.5 w-full justify-between">
						<div class="flex w-full justify-between">
							<div class=" self-center text-xs font-medium">{$i18n.t('WebUI URL')}</div>
						</div>

						<div class="flex mt-2 space-x-2">
							<input
								class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
								type="text"
								placeholder={`e.g.) "http://localhost:3000"`}
								bind:value={adminConfig.WEBUI_URL}
							/>
						</div>

						<div class="mt-2 text-xs text-gray-400 dark:text-gray-500">
							{$i18n.t(
								'Enter the public URL of your WebUI. This URL will be used to generate links in the notifications.'
							)}
						</div>
					</div>

					<div class=" w-full justify-between">
						<div class="flex w-full justify-between">
							<div class=" self-center text-xs font-medium">{$i18n.t('Webhook URL')}</div>
						</div>

						<div class="flex mt-2 space-x-2">
							<input
								class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
								type="text"
								placeholder={`https://example.com/webhook`}
								bind:value={webhookUrl}
							/>
						</div>
					</div>
				</div>
				{/if}
			</div>
		{/if}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
