<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { user, config } from '$lib/stores';
	import { getDemoSession } from '$lib/apis/verification';
	import { userSignOut } from '$lib/apis/auths';
	import { toast } from 'svelte-sonner';
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	let remaining: number | null = null;
	let enabled = false;
	let hasSession = false;
	let intervalId: ReturnType<typeof setInterval> | null = null;
	let warned15 = false;
	let warned5 = false;

	let showWarningModal = false;
	let warningMinutes = 0;

	function formatTime(seconds: number): string {
		const h = Math.floor(seconds / 3600);
		const m = Math.floor((seconds % 3600) / 60);
		const s = seconds % 60;
		return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
	}

	async function fetchSession() {
		try {
			const token = localStorage.getItem('token');
			if (!token) return;

			const data = await getDemoSession(token);
			if (data) {
				enabled = data.enabled;
				hasSession = data.has_session;
				if (data.remaining !== null && data.remaining !== undefined) {
					remaining = data.remaining;
				}
			}
		} catch (e) {
			console.error('Failed to fetch demo session:', e);
		}
	}

	async function handleExpired() {
		toast.error($i18n.t('Your session has expired. You will be logged out.'));
		try {
			await userSignOut();
		} catch (e) {
			// ignore
		}
		user.set(null);
		localStorage.removeItem('token');
		location.href = '/auth';
	}

	onMount(async () => {
		await fetchSession();

		if (enabled && hasSession) {
			intervalId = setInterval(() => {
				if (remaining !== null && remaining > 0) {
					remaining -= 1;

					// 15-minute warning
					if (remaining <= 900 && remaining > 895 && !warned15) {
						warned15 = true;
						warningMinutes = 15;
						showWarningModal = true;
					}

					// 5-minute warning
					if (remaining <= 300 && remaining > 295 && !warned5) {
						warned5 = true;
						warningMinutes = 5;
						showWarningModal = true;
					}

					// Expired
					if (remaining <= 0) {
						if (intervalId) clearInterval(intervalId);
						showWarningModal = false;
						handleExpired();
					}
				}
			}, 1000);
		}
	});

	onDestroy(() => {
		if (intervalId) clearInterval(intervalId);
	});
</script>

{#if enabled && hasSession && remaining !== null}
	<div
		class="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-mono shadow-lg
		{remaining <= 300
			? 'text-white demo-timer-blink'
			: remaining <= 900
				? 'bg-yellow-500 text-black'
				: 'bg-gray-800 text-white dark:bg-gray-700'}"
	>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			class="h-4 w-4"
			fill="none"
			viewBox="0 0 24 24"
			stroke="currentColor"
			stroke-width="2"
		>
			<circle cx="12" cy="12" r="10" />
			<polyline points="12 6 12 12 16 14" />
		</svg>
		<span>{formatTime(remaining)}</span>
	</div>
{/if}

{#if showWarningModal}
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-[9999]"
		on:mousedown|self={() => { showWarningModal = false; }}
	>
		<div
			class="bg-white dark:bg-gray-900 rounded-2xl shadow-3xl w-[24rem] max-w-[90vw] p-6"
			on:mousedown|stopPropagation
		>
			<div class="flex items-center gap-3 mb-4">
				<div class="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center
					{warningMinutes <= 5 ? 'bg-red-100 dark:bg-red-900/30' : 'bg-yellow-100 dark:bg-yellow-900/30'}"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="h-5 w-5 {warningMinutes <= 5 ? 'text-red-600 dark:text-red-400' : 'text-yellow-600 dark:text-yellow-400'}"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						stroke-width="2"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
					</svg>
				</div>
				<div class="text-lg font-semibold dark:text-gray-100">
					{$i18n.t('Session Reminder')}
				</div>
			</div>

			<p class="text-sm text-gray-600 dark:text-gray-300 mb-6">
				{warningMinutes <= 5
					? $i18n.t('You have 5 minutes remaining! Please save your work.')
					: $i18n.t('You have 15 minutes remaining.')}
			</p>

			<div class="flex justify-end">
				<button
					class="px-5 py-2 text-sm font-medium rounded-lg transition
						{warningMinutes <= 5
							? 'bg-red-600 hover:bg-red-700 text-white'
							: 'bg-yellow-500 hover:bg-yellow-600 text-black'}"
					on:click={() => { showWarningModal = false; }}
				>
					{$i18n.t('OK')}
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.demo-timer-blink {
		animation: timer-blink 1s ease-in-out infinite;
	}

	@keyframes timer-blink {
		0%, 100% {
			background-color: rgb(220, 38, 38);
		}
		50% {
			background-color: rgb(127, 29, 29);
		}
	}
</style>
