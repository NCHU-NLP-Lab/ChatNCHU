"""Write the new Permissions.svelte file."""

content = r'''<script lang="ts">
	import { getContext, onMount } from 'svelte';
	const i18n = getContext('i18n');

	import Switch from '$lib/components/common/Switch.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	const defaultPermissions = {
		workspace: { models: false, knowledge: false, prompts: false, tools: false },
		sharing: { public_models: false, public_knowledge: false, public_prompts: false, public_tools: false },
		chat: { controls: true, file_upload: true, delete: true, edit: true, stt: true, tts: true, call: true, multiple_models: true, temporary: true, temporary_enforced: false },
		features: { direct_tool_servers: false, web_search: true, image_generation: true, code_interpreter: true }
	};

	const defaultDemoLimits = {
		enable_demo_time_limit: false,
		demo_daily_login_limit: 1,
		demo_session_duration: 7200
	};

	export let permissions: any = {};
	export let custom = true;
	export let limitedAdmin = false;
	export let globalPermissions: any = null;
	export let globalDemoLimits: any = null;

	let useDefaultPermissions = true;
	let useDefaultDemoLimits = true;

	let permEdit: any = {};
	let demoEdit: any = {};
	let initialized = false;

	function initFromPermissions() {
		const p = permissions || {};
		const hasCustomPerms = p._customPermissions === true;
		const hasCustomDemo = p._customDemoLimits === true;
		useDefaultPermissions = !hasCustomPerms;
		useDefaultDemoLimits = !hasCustomDemo;

		const src = globalPermissions || defaultPermissions;
		permEdit = {
			workspace: { ...src.workspace, ...(hasCustomPerms ? p.workspace || {} : {}) },
			sharing: { ...src.sharing, ...(hasCustomPerms ? p.sharing || {} : {}) },
			chat: { ...src.chat, ...(hasCustomPerms ? p.chat || {} : {}) },
			features: { ...src.features, ...(hasCustomPerms ? p.features || {} : {}) },
			model: p.model || { filter: false, ids: [] }
		};

		const dSrc = globalDemoLimits || defaultDemoLimits;
		demoEdit = { ...dSrc, ...(hasCustomDemo ? p.demo_limits || {} : {}) };
		initialized = true;
	}

	function togglePermissions(val: boolean) {
		useDefaultPermissions = val;
		if (!val) {
			const src = globalPermissions || defaultPermissions;
			permEdit = {
				...permEdit,
				workspace: { ...src.workspace },
				sharing: { ...src.sharing },
				chat: { ...src.chat },
				features: { ...src.features }
			};
		}
		syncToPermissions();
	}

	function toggleDemoLimits(val: boolean) {
		useDefaultDemoLimits = val;
		if (!val) {
			const src = globalDemoLimits || defaultDemoLimits;
			demoEdit = { ...src };
		}
		syncToPermissions();
	}

	function syncToPermissions() {
		if (!initialized) return;
		const result: any = {};
		if (!useDefaultPermissions) {
			result._customPermissions = true;
			result.workspace = { ...permEdit.workspace };
			result.sharing = { ...permEdit.sharing };
			result.chat = { ...permEdit.chat };
			result.features = { ...permEdit.features };
			if (permEdit.model) result.model = permEdit.model;
		}
		if (custom && !useDefaultDemoLimits) {
			result._customDemoLimits = true;
			result.demo_limits = { ...demoEdit };
		}
		permissions = result;
	}

	$: if (initialized && permEdit) { syncToPermissions(); }
	$: if (initialized && demoEdit) { syncToPermissions(); }

	onMount(() => {
		initFromPermissions();
	});
</script>

<div>
	{#if !limitedAdmin}
	<!-- Permissions Section -->
	<div class="mb-2 flex w-full items-center justify-between pr-2">
		<div class="text-sm font-medium">{$i18n.t('Permissions')}</div>
		{#if custom}
			<div class="flex items-center gap-2">
				<div class="text-xs text-gray-500">{$i18n.t('Use Default')}</div>
				<Switch state={useDefaultPermissions} on:change={(e) => togglePermissions(e.detail)} />
			</div>
		{/if}
	</div>

	<hr class="border-gray-100 dark:border-gray-850 my-2" />

	{#if !useDefaultPermissions || !custom}

	<div>
		<div class="mb-2 text-sm font-medium">{$i18n.t('Workspace Permissions')}</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Models Access')}</div>
			<Switch bind:state={permEdit.workspace.models} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Knowledge Access')}</div>
			<Switch bind:state={permEdit.workspace.knowledge} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Prompts Access')}</div>
			<Switch bind:state={permEdit.workspace.prompts} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Tools Access')}</div>
			<Switch bind:state={permEdit.workspace.tools} />
		</div>
	</div>

	<hr class="border-gray-100 dark:border-gray-850 my-2" />

	<div>
		<div class="mb-2 text-sm font-medium">{$i18n.t('Sharing Permissions')}</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Public Models')}</div>
			<Switch bind:state={permEdit.sharing.public_models} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Public Knowledge')}</div>
			<Switch bind:state={permEdit.sharing.public_knowledge} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Public Prompts')}</div>
			<Switch bind:state={permEdit.sharing.public_prompts} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Public Tools')}</div>
			<Switch bind:state={permEdit.sharing.public_tools} />
		</div>
	</div>

	<hr class="border-gray-100 dark:border-gray-850 my-2" />

	<div>
		<div class="mb-2 text-sm font-medium">{$i18n.t('Chat Permissions')}</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Allow Chat Controls')}</div>
			<Switch bind:state={permEdit.chat.controls} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Allow File Upload')}</div>
			<Switch bind:state={permEdit.chat.file_upload} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Allow Chat Delete')}</div>
			<Switch bind:state={permEdit.chat.delete} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Allow Chat Edit')}</div>
			<Switch bind:state={permEdit.chat.edit} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Allow Speech-to-Text')}</div>
			<Switch bind:state={permEdit.chat.stt} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Allow Text-to-Speech')}</div>
			<Switch bind:state={permEdit.chat.tts} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Allow Voice Call')}</div>
			<Switch bind:state={permEdit.chat.call} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Allow Multiple Models')}</div>
			<Switch bind:state={permEdit.chat.multiple_models} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Allow Temporary Chat')}</div>
			<Switch bind:state={permEdit.chat.temporary} />
		</div>
		{#if permEdit.chat.temporary}
			<div class="flex w-full justify-between my-2 pr-2">
				<div class="self-center text-xs font-medium">
					<Tooltip content={$i18n.t('Enforce temporary chat for all users in this group')}>
						{$i18n.t('Enforce Temporary Chat')}
					</Tooltip>
				</div>
				<Switch bind:state={permEdit.chat.temporary_enforced} />
			</div>
		{/if}
	</div>

	<hr class="border-gray-100 dark:border-gray-850 my-2" />

	<div>
		<div class="mb-2 text-sm font-medium">{$i18n.t('Features Permissions')}</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Direct Tool Servers')}</div>
			<Switch bind:state={permEdit.features.direct_tool_servers} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Web Search')}</div>
			<Switch bind:state={permEdit.features.web_search} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Image Generation')}</div>
			<Switch bind:state={permEdit.features.image_generation} />
		</div>
		<div class="flex w-full justify-between my-2 pr-2">
			<div class="self-center text-xs font-medium">{$i18n.t('Code Interpreter')}</div>
			<Switch bind:state={permEdit.features.code_interpreter} />
		</div>
	</div>

	{:else}
		<div class="text-xs text-gray-400 dark:text-gray-500 py-3 text-center">
			{$i18n.t('Using default permissions. Turn off "Use Default" to customize.')}
		</div>
	{/if}
	{/if}

	{#if custom}
		{#if !limitedAdmin}
			<hr class="border-gray-100 dark:border-gray-850 my-2" />
		{/if}

		<!-- Demo Time Limit Section -->
		<div class="mb-2 flex w-full items-center justify-between pr-2">
			<div class="text-sm font-medium">{$i18n.t('Demo Time Limit')}</div>
			<div class="flex items-center gap-2">
				<div class="text-xs text-gray-500">{$i18n.t('Use Default')}</div>
				<Switch state={useDefaultDemoLimits} on:change={(e) => toggleDemoLimits(e.detail)} />
			</div>
		</div>

		<hr class="border-gray-100 dark:border-gray-850 my-2" />

		{#if !useDefaultDemoLimits}
			<div class="flex w-full items-center justify-between my-2 pr-2">
				<div class="self-center text-xs font-medium">
					{$i18n.t('Enable Daily Login Time Limit')}
				</div>
				<Switch bind:state={demoEdit.enable_demo_time_limit} />
			</div>

			{#if demoEdit.enable_demo_time_limit}
				<div class="mb-2.5">
					<div class="mb-1 text-xs font-medium">{$i18n.t('Daily Login Limit')}</div>
					<input
						class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850"
						type="number"
						min="1"
						bind:value={demoEdit.demo_daily_login_limit}
					/>
				</div>

				<div class="mb-2.5">
					<div class="mb-1 text-xs font-medium">{$i18n.t('Session Duration (seconds)')}</div>
					<input
						class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850"
						type="number"
						min="60"
						bind:value={demoEdit.demo_session_duration}
					/>
				</div>
			{/if}
		{:else}
			<div class="text-xs text-gray-400 dark:text-gray-500 py-3 text-center">
				{$i18n.t('Using default demo time limit settings. Turn off "Use Default" to customize.')}
			</div>
		{/if}
	{/if}
</div>
'''

out = 'src/lib/components/admin/Users/Groups/Permissions.svelte'
with open(out, 'wb') as f:
    f.write(content.encode().replace(b'\n', b'\r\n'))
print('Written OK')
