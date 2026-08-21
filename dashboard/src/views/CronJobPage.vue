<template>
  <div class="dashboard-page cron-page" :class="{ 'is-dark': isDark }">
    <v-container fluid class="dashboard-shell cron-shell pa-4 pa-md-6">
      <div class="cron-detail-width">
        <div class="cron-header mb-4 pb-4">
          <div class="cron-header-copy">
            <h1 class="dashboard-title">{{ tm("page.title") }}</h1>
            <div class="dashboard-subtitle">
              {{ tm("page.subtitle") }}
              <v-btn
                variant="text"
                color="primary"
                density="compact"
                class="supported-platform-link"
                @click="platformDialog = true"
              >
                {{ tm("page.proactive.link") }}
              </v-btn>
            </div>
          </div>

          <div class="cron-header-actions">
            <v-btn
              variant="text"
              color="primary"
              :loading="loading"
              prepend-icon="mdi-refresh"
              @click="loadJobs"
            >
              {{ tm("actions.refresh") }}
            </v-btn>
            <v-btn
              variant="tonal"
              color="primary"
              prepend-icon="mdi-plus"
              @click="openCreate"
            >
              {{ tm("actions.create") }}
            </v-btn>
          </div>
        </div>

        <section class="task-surface">
          <v-progress-linear
            v-if="loading && !jobs.length"
            indeterminate
            color="primary"
          />

          <div v-else-if="!jobs.length" class="cron-empty-state">
            <v-icon size="64" color="grey-lighten-1">
              mdi-calendar-blank-outline
            </v-icon>
            <p class="text-grey mt-4">{{ tm("table.empty") }}</p>
          </div>

          <template v-else>
            <div class="task-filter-bar">
              <v-text-field
                v-model="taskSearch"
                :label="tm('filters.search')"
                prepend-inner-icon="mdi-magnify"
                variant="solo-filled"
                density="compact"
                clearable
                hide-details
              />
              <v-autocomplete
                v-model="selectedUmoFilter"
                :items="jobUmoFilterOptions"
                item-title="label"
                item-value="value"
                :label="tm('filters.umo')"
                prepend-inner-icon="mdi-send-outline"
                variant="solo-filled"
                density="compact"
                clearable
                hide-details
                :no-data-text="tm('filters.noUmos')"
              />
              <div class="task-bulk-actions">
                <v-checkbox-btn
                  :model-value="allVisibleJobsSelected"
                  :indeterminate="
                    someVisibleJobsSelected && !allVisibleJobsSelected
                  "
                  density="compact"
                  color="primary"
                  class="task-select-all"
                  @click.stop
                  @update:model-value="toggleAllVisibleJobs"
                />
                <span class="task-selected-count">
                  {{ tm("bulk.selected", { count: selectedJobIds.size }) }}
                </span>
                <v-btn
                  variant="tonal"
                  color="error"
                  size="small"
                  prepend-icon="mdi-delete-sweep-outline"
                  :disabled="!selectedJobIds.size"
                  :loading="bulkDeleting"
                  class="task-bulk-delete-btn"
                  @click="deleteSelectedJobs"
                >
                  {{ tm("actions.batchDelete") }}
                </v-btn>
              </div>
            </div>

            <div v-if="!sortedJobs.length" class="cron-empty-state">
              <v-icon size="64" color="grey-lighten-1">
                mdi-file-search-outline
              </v-icon>
              <p class="text-grey mt-4">{{ tm("filters.noMatches") }}</p>
            </div>

            <div v-else class="task-list pb-3">
              <OutlinedActionListItem
                v-for="item in sortedJobs"
                :key="item.job_id"
                :class="`task-item--${readScheduleFromJob(item).schedule_mode}`"
                :title="item.name || tm('table.notAvailable')"
                clickable
                @click="openEdit(item)"
              >
                <template #title-prepend>
                  <v-checkbox-btn
                    :model-value="selectedJobIds.has(String(item.job_id || ''))"
                    density="compact"
                    color="primary"
                    class="task-card-checkbox"
                    @click.stop
                    @update:model-value="
                      (selected) => setJobSelection(item.job_id, !!selected)
                    "
                  />
                </template>

                <template #title-extra>
                  <v-chip
                    size="x-small"
                    variant="flat"
                    class="schedule-type-chip"
                  >
                    {{ scheduleProductLabel(item) }}
                  </v-chip>
                </template>

                <div class="task-description">
                  {{ taskPreview(item) }}
                </div>

                <div class="task-meta">
                  <span class="task-meta-item">
                    <v-icon size="small" class="me-1">mdi-send-outline</v-icon>
                    {{ deliveryTargetText(item) }}
                  </span>
                  <v-tooltip :text="lastRunTooltipText(item)" location="top">
                    <template #activator="{ props }">
                      <span v-bind="props" class="task-meta-item">
                        <v-icon size="small" class="me-1">
                          mdi-clock-time-four-outline
                        </v-icon>
                        {{ nextRunText(item) }}
                      </span>
                    </template>
                  </v-tooltip>
                </div>

                <template #actions>
                  <div class="task-inline-actions">
                    <v-btn
                      variant="tonal"
                      size="small"
                      prepend-icon="mdi-pencil-outline"
                      class="task-inline-action-btn task-inline-action-btn--edit"
                      @click.stop="openEdit(item)"
                    >
                      {{ tm("actions.edit") }}
                    </v-btn>
                    <v-btn
                      variant="tonal"
                      size="small"
                      prepend-icon="mdi-play-circle-outline"
                      :disabled="runningJobIds.has(item.job_id)"
                      class="task-inline-action-btn task-inline-action-btn--run"
                      @click.stop="runJobNow(item)"
                    >
                      {{ tm("actions.runNow") }}
                    </v-btn>
                    <v-btn
                      variant="tonal"
                      size="small"
                      prepend-icon="mdi-delete-outline"
                      class="task-inline-action-btn task-inline-action-btn--danger"
                      @click.stop="deleteJob(item)"
                    >
                      {{ tm("actions.delete") }}
                    </v-btn>
                  </div>
                </template>

                <template #control>
                  <v-switch
                    v-model="item.enabled"
                    inset
                    density="compact"
                    hide-details
                    color="primary"
                    @click.stop
                    @change="toggleJob(item)"
                  />
                </template>
              </OutlinedActionListItem>
            </div>
          </template>
        </section>

        <v-dialog v-model="platformDialog" max-width="560">
          <v-card class="platform-dialog-card">
            <v-card-title class="platform-dialog-title">
              <span class="platform-dialog-title__mark"></span>
              <span class="platform-dialog-title__copy">
                <span>{{ tm("platformDialog.title") }}</span>
                <small>已支持 {{ proactivePlatforms.length }} 个平台主动推送</small>
              </span>
            </v-card-title>
            <v-card-text class="platform-dialog-body">
              <div class="platform-dialog-note">
                {{ tm("platformDialog.description") }}
              </div>
              <div v-if="proactivePlatforms.length" class="platform-list">
                <div
                  v-for="platform in proactivePlatforms"
                  :key="platform.id"
                  class="platform-list-item"
                >
                  <div class="platform-list-item__badge">
                    {{ (platform.display_name || platform.name || platform.id).slice(0, 1).toUpperCase() }}
                  </div>
                  <div class="platform-list-item__content">
                    <div class="platform-name">
                      {{ platform.display_name || platform.name }}
                    </div>
                    <div class="platform-id">{{ platform.id }}</div>
                  </div>
                  <div class="platform-list-item__status">支持主动推送</div>
                </div>
              </div>
              <div v-else class="dashboard-empty platform-dialog-empty">
                {{ tm("page.proactive.unsupported") }}
              </div>
            </v-card-text>
            <v-card-actions class="platform-dialog-actions">
              <v-spacer></v-spacer>
              <v-btn
                class="platform-dialog-close-btn"
                color="primary"
                variant="tonal"
                @click="platformDialog = false"
              >
                {{ tm("actions.close") }}
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>

        <v-snackbar
          v-model="snackbar.show"
          :color="snackbar.color"
          timeout="2600"
        >
          {{ snackbar.message }}
        </v-snackbar>

        <v-dialog v-model="createDialog" max-width="760" scrollable>
          <v-card class="dashboard-dialog-card cron-job-dialog-card">
            <v-card-title
              class="text-h3 pa-4 pb-0 pl-6 cron-job-dialog-title"
              >{{ dialogTitle }}</v-card-title
            >
            <v-card-text class="cron-job-dialog-body">
              <div class="dashboard-form-grid dashboard-form-grid--single">
                <v-text-field
                  v-model="newJob.name"
                  :label="tm('form.name')"
                  variant="outlined"
                  density="comfortable"
                />
                <v-textarea
                  v-model="newJob.note"
                  :label="tm('form.note')"
                  variant="outlined"
                  density="comfortable"
                  rows="5"
                />

                <div class="schedule-field">
                  <v-select
                    v-model="newJob.schedule_mode"
                    :class="[
                      'schedule-mode-select',
                      scheduleTypeClass(newJob.schedule_mode),
                    ]"
                    :items="scheduleModeOptions"
                    item-title="label"
                    item-value="value"
                    :label="tm('form.scheduleMode')"
                    variant="outlined"
                    density="comfortable"
                    hide-details
                    :menu-props="{ contentClass: 'schedule-mode-menu' }"
                  >
                    <template #selection="{ item }">
                      <span
                        :class="[
                          'schedule-mode-selection',
                          scheduleTypeClass(item.raw.value),
                        ]"
                      >
                        <span class="schedule-mode-dot" />
                        {{ item.raw.label }}
                      </span>
                    </template>
                    <template #item="{ props, item }">
                      <v-list-item
                        v-bind="props"
                        :class="[
                          'schedule-mode-option',
                          scheduleTypeClass(item.raw.value),
                        ]"
                      >
                        <template #prepend>
                          <span class="schedule-mode-dot" />
                        </template>
                      </v-list-item>
                    </template>
                  </v-select>

                  <v-text-field
                    v-if="newJob.schedule_mode === 'once'"
                    v-model="newJob.run_at"
                    :label="tm('form.runAt')"
                    type="datetime-local"
                    variant="outlined"
                    density="comfortable"
                    hide-details
                  />

                  <div
                    v-else-if="newJob.schedule_mode === 'interval'"
                    class="schedule-inline-fields"
                  >
                    <v-text-field
                      v-model.number="newJob.interval_value"
                      :label="tm('form.intervalEvery')"
                      type="number"
                      min="1"
                      variant="outlined"
                      density="comfortable"
                      hide-details
                    />
                    <v-select
                      v-model="newJob.interval_unit"
                      :items="intervalUnitOptions"
                      item-title="label"
                      item-value="value"
                      :label="tm('form.intervalUnit')"
                      variant="outlined"
                      density="comfortable"
                      hide-details
                    />
                  </div>

                  <v-text-field
                    v-else-if="newJob.schedule_mode === 'daily'"
                    v-model="newJob.daily_time"
                    :label="tm('form.dailyTime')"
                    type="time"
                    variant="outlined"
                    density="comfortable"
                    hide-details
                  />

                  <div
                    v-else-if="newJob.schedule_mode === 'weekly'"
                    class="schedule-inline-fields"
                  >
                    <v-select
                      v-model="newJob.weekly_day"
                      :items="weekdayOptions"
                      item-title="label"
                      item-value="value"
                      :label="tm('form.weeklyDay')"
                      variant="outlined"
                      density="comfortable"
                      hide-details
                    />
                    <v-text-field
                      v-model="newJob.weekly_time"
                      :label="tm('form.weeklyTime')"
                      type="time"
                      variant="outlined"
                      density="comfortable"
                      hide-details
                    />
                  </div>

                  <div
                    v-else-if="newJob.schedule_mode === 'monthly'"
                    class="schedule-inline-fields"
                  >
                    <v-text-field
                      v-model.number="newJob.monthly_day"
                      :label="tm('form.monthlyDay')"
                      type="number"
                      min="1"
                      max="31"
                      variant="outlined"
                      density="comfortable"
                      hide-details
                    />
                    <v-text-field
                      v-model="newJob.monthly_time"
                      :label="tm('form.monthlyTime')"
                      type="time"
                      variant="outlined"
                      density="comfortable"
                      hide-details
                    />
                  </div>

                  <v-text-field
                    v-else
                    v-model="newJob.cron_expression"
                    :label="tm('form.cron')"
                    :placeholder="tm('form.cronPlaceholder')"
                    variant="outlined"
                    density="comfortable"
                    hide-details
                  />
                </div>

                <v-autocomplete
                  v-model="newJob.session"
                  :items="availableUmos"
                  :loading="loadingUmos"
                  :label="tm('form.session')"
                  variant="outlined"
                  density="comfortable"
                  clearable
                  hide-details
                  :no-data-text="tm('form.noUmos')"
                  :menu-props="{ contentClass: 'cron-umo-menu' }"
                  @focus="loadUmos()"
                >
                  <template #item="{ props, item }">
                    <v-list-item v-bind="props">
                      <template #title>
                        <UmoDisplay
                          v-bind="getUmoDisplayProps(item.raw)"
                          compact
                          :show-info="false"
                          :show-platform="false"
                        />
                      </template>
                      <template #append>
                        <v-chip
                          v-if="getUmoInfo(item.raw).platform"
                          size="x-small"
                          variant="flat"
                          class="cron-umo-platform"
                        >
                          {{ getUmoInfo(item.raw).platform }}
                        </v-chip>
                      </template>
                    </v-list-item>
                  </template>
                  <template #selection="{ item }">
                    <v-chip
                      v-if="item && getUmoSelectionText(item.raw)"
                      size="small"
                      variant="tonal"
                      color="primary"
                      class="umo-selection-chip"
                    >
                      {{ getUmoSelectionText(item.raw) }}
                    </v-chip>
                  </template>
                </v-autocomplete>
              </div>
            </v-card-text>
            <v-card-actions class="cron-job-dialog-actions">
              <v-spacer />
              <v-btn
                variant="tonal"
                class="cron-job-secondary-btn"
                @click="createDialog = false"
                >{{ tm("actions.cancel") }}</v-btn
              >
              <v-btn
                variant="flat"
                color="primary"
                class="cron-job-primary-btn"
                :loading="creating"
                @click="submitJob"
              >
                {{ dialogSubmitText }}
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>
      </div>
    </v-container>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useTheme } from "vuetify";
import { botApi, cronApi, sessionApi } from "@/api/v1";
import { useModuleI18n } from "@/i18n/composables";
import { askForConfirmation, useConfirmDialog } from "@/utils/confirmDialog";
import OutlinedActionListItem from "@/components/shared/OutlinedActionListItem.vue";
import UmoDisplay from "@/components/shared/UmoDisplay.vue";

const { tm } = useModuleI18n("features/cron");
const theme = useTheme();
const confirmDialog = useConfirmDialog();

const isDark = computed(() => theme.global.current.value.dark);
const loading = ref(false);
const jobs = ref<any[]>([]);
const taskSearch = ref("");
const selectedUmoFilter = ref<string | null>(null);
const selectedJobIds = ref(new Set<string>());
const proactivePlatforms = ref<
  { id: string; name: string; display_name?: string }[]
>([]);
const availableUmos = ref<string[]>([]);
const availableUmoInfoMap = ref<Record<string, UmoInfo>>({});
const loadingUmos = ref(false);
const platformDialog = ref(false);
const createDialog = ref(false);
const creating = ref(false);
const bulkDeleting = ref(false);
const editingJobId = ref("");
const runningJobIds = ref(new Set<string>());
const NO_DELIVERY_TARGET_FILTER = "__astrbot_no_delivery_target__";
type ScheduleMode =
  | "once"
  | "interval"
  | "daily"
  | "weekly"
  | "monthly"
  | "cron";
type IntervalUnit = "minutes" | "hours" | "days";
type UmoInfo = {
  umo: string;
  platform?: string;
  message_type?: string;
  session_id?: string;
  auto_name?: string;
  user_alias?: string;
  display_name?: string;
};

const newJob = ref({
  schedule_mode: "once" as ScheduleMode,
  name: "",
  note: "",
  cron_expression: "",
  run_at: "",
  interval_value: 1,
  interval_unit: "hours" as IntervalUnit,
  daily_time: "09:00",
  weekly_day: 1,
  weekly_time: "09:00",
  monthly_day: 1,
  monthly_time: "09:00",
  session: "",
  timezone: "",
  enabled: true,
});

const snackbar = ref({ show: false, message: "", color: "success" });

const jobUmoFilterOptions = computed(() => [
  ...(jobs.value.some((job) => !getJobSession(job))
    ? [
        {
          label: tm("filters.noDeliveryTarget"),
          value: NO_DELIVERY_TARGET_FILTER,
        },
      ]
    : []),
  ...Array.from(new Set(jobs.value.map(getJobSession).filter(Boolean)))
    .sort((a, b) => a.localeCompare(b))
    .map((umo) => ({ label: umo, value: umo })),
]);

const filteredJobs = computed(() => {
  const query = taskSearch.value.trim().toLowerCase();
  const umo = selectedUmoFilter.value;
  return jobs.value.filter((job) => {
    const session = getJobSession(job);
    if (umo === NO_DELIVERY_TARGET_FILTER && session) {
      return false;
    }
    if (umo && umo !== NO_DELIVERY_TARGET_FILTER && session !== umo) {
      return false;
    }

    if (!query) {
      return true;
    }

    const title = String(job.name || "").toLowerCase();
    const content = String(job.note || job.description || "").toLowerCase();
    return title.includes(query) || content.includes(query);
  });
});

const sortedJobs = computed(() =>
  [...filteredJobs.value].sort((a, b) => {
    if (a.enabled !== b.enabled) {
      return a.enabled ? -1 : 1;
    }

    const nextA = parseTimeValue(a.next_run_time ?? a.run_at);
    const nextB = parseTimeValue(b.next_run_time ?? b.run_at);

    if (nextA !== nextB) {
      if (!nextA) return 1;
      if (!nextB) return -1;
      return nextA - nextB;
    }

    return String(a.name || "").localeCompare(String(b.name || ""));
  }),
);

const visibleJobIds = computed(() =>
  sortedJobs.value.map((job) => String(job.job_id || "")).filter(Boolean),
);
const someVisibleJobsSelected = computed(() =>
  visibleJobIds.value.some((jobId) => selectedJobIds.value.has(jobId)),
);
const allVisibleJobsSelected = computed(
  () =>
    !!visibleJobIds.value.length &&
    visibleJobIds.value.every((jobId) => selectedJobIds.value.has(jobId)),
);
const isEditing = computed(() => !!editingJobId.value);
const dialogTitle = computed(() =>
  tm(isEditing.value ? "form.editTitle" : "form.title"),
);
const dialogSubmitText = computed(() =>
  tm(isEditing.value ? "actions.save" : "actions.submit"),
);
const scheduleModeOptions = computed(() => [
  { label: tm("form.scheduleModes.once"), value: "once" },
  { label: tm("form.scheduleModes.interval"), value: "interval" },
  { label: tm("form.scheduleModes.daily"), value: "daily" },
  { label: tm("form.scheduleModes.weekly"), value: "weekly" },
  { label: tm("form.scheduleModes.monthly"), value: "monthly" },
  { label: tm("form.scheduleModes.cron"), value: "cron" },
]);
const intervalUnitOptions = computed(() => [
  { label: tm("form.intervalUnits.minutes"), value: "minutes" },
  { label: tm("form.intervalUnits.hours"), value: "hours" },
  { label: tm("form.intervalUnits.days"), value: "days" },
]);
const weekdayOptions = computed(() => [
  { label: tm("form.weekdays.sunday"), value: 0 },
  { label: tm("form.weekdays.monday"), value: 1 },
  { label: tm("form.weekdays.tuesday"), value: 2 },
  { label: tm("form.weekdays.wednesday"), value: 3 },
  { label: tm("form.weekdays.thursday"), value: 4 },
  { label: tm("form.weekdays.friday"), value: 5 },
  { label: tm("form.weekdays.saturday"), value: 6 },
]);

function toast(
  message: string,
  color: "success" | "error" | "warning" = "success",
) {
  snackbar.value = { show: true, message, color };
}

function parseTimeValue(value: any): number {
  if (!value) return 0;
  const ts = new Date(value).getTime();
  return Number.isNaN(ts) ? 0 : ts;
}

function formatTime(val: any, fallback = tm("table.notAvailable")): string {
  if (!val) return fallback;
  try {
    const date = new Date(val);
    return Number.isNaN(date.getTime()) ? fallback : date.toLocaleString();
  } catch {
    return String(val);
  }
}

function taskPreview(item: any): string {
  const text = String(item.note || item.description || "").trim();
  if (!text) return item.job_id || tm("table.notAvailable");
  return text.length > 86 ? `${text.slice(0, 86)}...` : text;
}

function getJobSession(job: any): string {
  return String(job.session || job?.payload?.session || "").trim();
}

function deliveryTargetText(item: any): string {
  return getJobSession(item) || tm("card.noDeliveryTarget");
}

function nextRunText(item: any): string {
  if (item.run_once) {
    return tm("card.runAt", { time: formatTime(item.run_at) });
  }
  return tm("card.nextRun", {
    time: formatTime(item.next_run_time, tm("table.notAvailable")),
  });
}

function lastRunTooltipText(item: any): string {
  const lastRun = `${tm("table.headers.lastRun")}: ${formatTime(
    item.last_run_at,
  )}`;
  const lastError = String(item.last_error || "").trim();
  if (!lastError) {
    return lastRun;
  }
  return `${lastRun} · ${lastError}`;
}

function scheduleProductLabel(item: any): string {
  if (item.run_once) {
    return tm("card.onceAt", { time: formatTime(item.run_at) });
  }

  const cron = String(item.cron_expression || "").trim();
  const parts = cron.split(/\s+/);
  if (parts.length !== 5) {
    return cron || tm("table.notAvailable");
  }

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;
  const minuteInterval = /^\*\/(\d+)$/.exec(minute);
  if (
    minuteInterval &&
    hour === "*" &&
    dayOfMonth === "*" &&
    month === "*" &&
    dayOfWeek === "*"
  ) {
    return tm("card.everyMinutes", { count: Number(minuteInterval[1]) });
  }

  const hourInterval = /^\*\/(\d+)$/.exec(hour);
  if (
    minute === "0" &&
    hourInterval &&
    dayOfMonth === "*" &&
    month === "*" &&
    dayOfWeek === "*"
  ) {
    return tm("card.everyHours", { count: Number(hourInterval[1]) });
  }

  const dayInterval = /^\*\/(\d+)$/.exec(dayOfMonth);
  if (
    minute === "0" &&
    hour === "0" &&
    dayInterval &&
    month === "*" &&
    dayOfWeek === "*"
  ) {
    return tm("card.everyDays", { count: Number(dayInterval[1]) });
  }

  const minuteNumber = Number(minute);
  const hourNumber = Number(hour);
  const dayOfMonthNumber = Number(dayOfMonth);
  const dayOfWeekNumber = Number(dayOfWeek);
  if (!isCronTime(minuteNumber, hourNumber)) {
    return tm("card.customCron", { cron });
  }
  const time = `${padTimePart(hourNumber)}:${padTimePart(minuteNumber)}`;
  if (dayOfMonth === "*" && month === "*" && dayOfWeek === "*") {
    return tm("card.dailyAt", { time });
  }
  if (
    dayOfMonth === "*" &&
    month === "*" &&
    Number.isInteger(dayOfWeekNumber) &&
    dayOfWeekNumber >= 0 &&
    dayOfWeekNumber <= 6
  ) {
    return tm("card.weeklyAt", {
      day: weekdayText(dayOfWeekNumber),
      time,
    });
  }
  if (
    Number.isInteger(dayOfMonthNumber) &&
    dayOfMonthNumber >= 1 &&
    dayOfMonthNumber <= 31 &&
    month === "*" &&
    dayOfWeek === "*"
  ) {
    return tm("card.monthlyAt", { day: dayOfMonthNumber, time });
  }
  return tm("card.customCron", { cron });
}

function weekdayText(value: number): string {
  const keyMap = [
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
  ];
  return tm(`form.weekdays.${keyMap[value]}`);
}

function parseUmoInfo(umo: string): UmoInfo {
  const parts = umo.split(":");
  return {
    umo,
    platform: parts[0] || "",
    message_type: parts[1] || "",
    session_id: parts.slice(2).join(":") || umo,
    auto_name: "",
    user_alias: "",
    display_name: umo,
  };
}

function mergeUmoInfos(infos: UmoInfo[] = []) {
  const next = { ...availableUmoInfoMap.value };
  for (const info of infos) {
    if (info?.umo) {
      next[info.umo] = { ...(next[info.umo] || {}), ...info };
    }
  }
  availableUmoInfoMap.value = next;
}

function getUmoInfo(umo: string): UmoInfo {
  return availableUmoInfoMap.value[umo] || parseUmoInfo(umo);
}

function getUmoDisplayProps(umo: string) {
  const info = getUmoInfo(umo);
  return {
    umo,
    platform: info.platform || "",
    messageType: info.message_type || "",
    sessionId: info.session_id || "",
    autoName: info.auto_name || "",
    userAlias: info.user_alias || "",
  };
}

function getPlatformColor(platform = "") {
  const colors: Record<string, string> = {
    aiocqhttp: "blue",
    qq_official: "purple",
    telegram: "light-blue",
    discord: "indigo",
    webchat: "orange",
  };
  return colors[platform] || "grey";
}

function getUmoSelectionText(value?: string | null): string {
  if (!value) return "";
  const info = getUmoInfo(value);
  const aliasName = info.user_alias || "";
  const autoName = info.auto_name || "";
  if (aliasName && autoName && aliasName !== autoName) {
    return `${aliasName}（${autoName}）`;
  }
  return aliasName || autoName || value || info.display_name || "";
}

async function loadUmos(force = false) {
  if (loadingUmos.value || (!force && availableUmos.value.length)) return;
  loadingUmos.value = true;
  try {
    const res = await sessionApi.activeUmos();
    if (res.data.status === "ok") {
      const loadedUmos = Array.isArray(res.data.data?.umos)
        ? res.data.data.umos
        : [];
      mergeUmoInfos(res.data.data?.umo_infos || []);
      availableUmos.value = Array.from(
        new Set([...availableUmos.value, ...loadedUmos]),
      );
    }
  } catch {
    // The field remains editable through free search only when a UMO list is available.
  } finally {
    loadingUmos.value = false;
  }
}

async function loadJobs() {
  loading.value = true;
  try {
    const res = await cronApi.list();
    if (res.data.status === "ok") {
      const data = Array.isArray(res.data.data) ? res.data.data : [];
      jobs.value = data.map((job: any) => ({
        ...job,
        session: job?.payload?.session || job?.session || "",
      }));
      mergeUmoInfos(
        jobs.value.map(getJobSession).filter(Boolean).map(parseUmoInfo),
      );
      const nextJobIds = new Set(jobs.value.map((job) => String(job.job_id)));
      selectedJobIds.value = new Set(
        [...selectedJobIds.value].filter((jobId) => nextJobIds.has(jobId)),
      );
    } else {
      toast(res.data.message || tm("messages.loadFailed"), "error");
    }
  } catch (e: any) {
    toast(e?.response?.data?.message || tm("messages.loadFailed"), "error");
  } finally {
    loading.value = false;
  }
}

async function loadPlatforms() {
  try {
    const res = await botApi.stats();
    if (res.data.status === "ok" && Array.isArray(res.data.data?.platforms)) {
      proactivePlatforms.value = res.data.data.platforms
        .filter((p: any) => p?.meta?.support_proactive_message)
        .map((p: any) => ({
          id: p?.id || p?.meta?.id || "unknown",
          name: p?.meta?.name || p?.type || "",
          display_name: p?.meta?.display_name || p?.display_name,
        }));
    }
  } catch {
    // Ignore platform fetch failures and keep the fallback state.
  }
}

function setJobSelection(jobId: string, selected: boolean) {
  const id = String(jobId || "");
  if (!id) return;
  const next = new Set(selectedJobIds.value);
  if (selected) {
    next.add(id);
  } else {
    next.delete(id);
  }
  selectedJobIds.value = next;
}

function toggleAllVisibleJobs(selected: boolean | null) {
  const next = new Set(selectedJobIds.value);
  for (const jobId of visibleJobIds.value) {
    if (selected) {
      next.add(jobId);
    } else {
      next.delete(jobId);
    }
  }
  selectedJobIds.value = next;
}

async function toggleJob(job: any) {
  try {
    const res = await cronApi.update(job.job_id, {
      enabled: job.enabled,
    });
    if (res.data.status !== "ok") {
      toast(res.data.message || tm("messages.updateFailed"), "error");
      await loadJobs();
    }
  } catch (e: any) {
    toast(e?.response?.data?.message || tm("messages.updateFailed"), "error");
    await loadJobs();
  }
}

async function deleteJob(job: any) {
  try {
    const res = await cronApi.delete(job.job_id);
    if (res.data.status === "ok") {
      toast(tm("messages.deleteSuccess"));
      jobs.value = jobs.value.filter(
        (item) => String(item.job_id) !== String(job.job_id),
      );
      setJobSelection(job.job_id, false);
    } else {
      toast(res.data.message || tm("messages.deleteFailed"), "error");
    }
  } catch (e: any) {
    toast(e?.response?.data?.message || tm("messages.deleteFailed"), "error");
  }
}

async function deleteSelectedJobs() {
  const jobIds = [...selectedJobIds.value];
  if (!jobIds.length || bulkDeleting.value) return;
  const confirmed = await askForConfirmation(
    tm("messages.batchDeleteConfirm", { count: jobIds.length }),
    confirmDialog,
  );
  if (!confirmed) return;

  bulkDeleting.value = true;
  try {
    const results = await Promise.allSettled(
      jobIds.map(async (jobId) => {
        const res = await cronApi.delete(jobId);
        if (res.data.status !== "ok") {
          throw new Error(res.data.message || tm("messages.deleteFailed"));
        }
        return jobId;
      }),
    );
    const deletedIds = results
      .filter(
        (result): result is PromiseFulfilledResult<string> =>
          result.status === "fulfilled",
      )
      .map((result) => result.value);
    const deletedIdSet = new Set(deletedIds);

    jobs.value = jobs.value.filter(
      (item) => !deletedIdSet.has(String(item.job_id)),
    );
    selectedJobIds.value = new Set(
      [...selectedJobIds.value].filter((jobId) => !deletedIdSet.has(jobId)),
    );

    const failedCount = results.length - deletedIds.length;
    if (failedCount) {
      toast(
        tm("messages.batchDeletePartial", {
          deleted: deletedIds.length,
          failed: failedCount,
        }),
        "error",
      );
    } else {
      toast(tm("messages.batchDeleteSuccess", { count: deletedIds.length }));
    }
  } catch (e: any) {
    toast(e?.response?.data?.message || tm("messages.deleteFailed"), "error");
  } finally {
    bulkDeleting.value = false;
  }
}

async function runJobNow(job: any) {
  const jobId = String(job.job_id || "");
  if (!jobId || runningJobIds.value.has(jobId)) return;
  runningJobIds.value = new Set([...runningJobIds.value, jobId]);
  try {
    const res = await cronApi.run(jobId);
    if (res.data.status === "ok") {
      toast(tm("messages.runStarted"));
      await loadJobs();
    } else {
      toast(res.data.message || tm("messages.runFailed"), "error");
    }
  } catch (e: any) {
    toast(e?.response?.data?.message || tm("messages.runFailed"), "error");
  } finally {
    const next = new Set(runningJobIds.value);
    next.delete(jobId);
    runningJobIds.value = next;
  }
}

function openCreate() {
  editingJobId.value = "";
  resetNewJob();
  createDialog.value = true;
  loadUmos();
}

function toDatetimeLocalValue(value: any): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset();
  const local = new Date(date.getTime() - offset * 60_000);
  return local.toISOString().slice(0, 16);
}

function toIsoDatetime(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toISOString();
}

function resetNewJob() {
  newJob.value = {
    schedule_mode: "once",
    name: "",
    note: "",
    cron_expression: "",
    run_at: "",
    interval_value: 1,
    interval_unit: "hours",
    daily_time: "09:00",
    weekly_day: 1,
    weekly_time: "09:00",
    monthly_day: 1,
    monthly_time: "09:00",
    session: "",
    timezone: "",
    enabled: true,
  };
}

function openEdit(job: any) {
  editingJobId.value = job.job_id;
  const schedule = readScheduleFromJob(job);
  if (job.session && !availableUmos.value.includes(job.session)) {
    availableUmos.value = [job.session, ...availableUmos.value];
    mergeUmoInfos([parseUmoInfo(job.session)]);
  }
  newJob.value = {
    schedule_mode: schedule.schedule_mode,
    name: job.name || "",
    note: job.note || job.description || "",
    cron_expression: schedule.cron_expression,
    run_at: toDatetimeLocalValue(job.run_at),
    interval_value: schedule.interval_value,
    interval_unit: schedule.interval_unit,
    daily_time: schedule.daily_time,
    weekly_day: schedule.weekly_day,
    weekly_time: schedule.weekly_time,
    monthly_day: schedule.monthly_day,
    monthly_time: schedule.monthly_time,
    session: job.session || job?.payload?.session || "",
    timezone: job.timezone || "",
    enabled: job.enabled !== false,
  };
  createDialog.value = true;
  loadUmos(true);
}

function parseTimeParts(
  value: string,
): { hour: number; minute: number } | null {
  const match = /^(\d{2}):(\d{2})(?::\d{2})?$/.exec(value || "");
  if (!match) return null;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
  return { hour, minute };
}

function padTimePart(value: string | number): string {
  return String(value).padStart(2, "0");
}

function isCronTime(minute: number, hour: number): boolean {
  return (
    Number.isInteger(minute) &&
    minute >= 0 &&
    minute <= 59 &&
    Number.isInteger(hour) &&
    hour >= 0 &&
    hour <= 23
  );
}

function buildCronExpression(): string {
  const mode = newJob.value.schedule_mode;
  if (mode === "interval") {
    const value = Math.max(1, Number(newJob.value.interval_value || 1));
    if (newJob.value.interval_unit === "minutes") {
      return `*/${Math.min(value, 59)} * * * *`;
    }
    if (newJob.value.interval_unit === "hours") {
      return `0 */${Math.min(value, 23)} * * *`;
    }
    return `0 0 */${Math.min(value, 31)} * *`;
  }
  if (mode === "daily") {
    const time = parseTimeParts(newJob.value.daily_time);
    if (!time) return "";
    return `${time.minute} ${time.hour} * * *`;
  }
  if (mode === "weekly") {
    const time = parseTimeParts(newJob.value.weekly_time);
    if (!time) return "";
    const weekday = Math.min(Math.max(Number(newJob.value.weekly_day), 0), 6);
    return `${time.minute} ${time.hour} * * ${weekday}`;
  }
  if (mode === "monthly") {
    const time = parseTimeParts(newJob.value.monthly_time);
    if (!time) return "";
    const day = Math.min(
      Math.max(Number(newJob.value.monthly_day || 1), 1),
      31,
    );
    return `${time.minute} ${time.hour} ${day} * *`;
  }
  return newJob.value.cron_expression.trim();
}

function readScheduleFromJob(job: any) {
  const fallback = {
    schedule_mode: "cron" as ScheduleMode,
    cron_expression: job.cron_expression || "",
    interval_value: 1,
    interval_unit: "hours" as IntervalUnit,
    daily_time: "09:00",
    weekly_day: 1,
    weekly_time: "09:00",
    monthly_day: 1,
    monthly_time: "09:00",
  };
  if (job.run_once) {
    return { ...fallback, schedule_mode: "once" as ScheduleMode };
  }

  const cron = String(job.cron_expression || "").trim();
  const parts = cron.split(/\s+/);
  if (parts.length !== 5) {
    return fallback;
  }

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;
  const minuteNumber = Number(minute);
  const hourNumber = Number(hour);
  const dayOfMonthNumber = Number(dayOfMonth);
  const dayOfWeekNumber = Number(dayOfWeek);
  const hasCronTime = isCronTime(minuteNumber, hourNumber);
  const time = hasCronTime
    ? `${padTimePart(hourNumber)}:${padTimePart(minuteNumber)}`
    : "09:00";

  const minuteInterval = /^\*\/(\d+)$/.exec(minute);
  if (
    minuteInterval &&
    hour === "*" &&
    dayOfMonth === "*" &&
    month === "*" &&
    dayOfWeek === "*"
  ) {
    return {
      ...fallback,
      schedule_mode: "interval" as ScheduleMode,
      interval_value: Number(minuteInterval[1]),
      interval_unit: "minutes" as IntervalUnit,
    };
  }

  const hourInterval = /^\*\/(\d+)$/.exec(hour);
  if (
    minute === "0" &&
    hourInterval &&
    dayOfMonth === "*" &&
    month === "*" &&
    dayOfWeek === "*"
  ) {
    return {
      ...fallback,
      schedule_mode: "interval" as ScheduleMode,
      interval_value: Number(hourInterval[1]),
      interval_unit: "hours" as IntervalUnit,
    };
  }

  const dayInterval = /^\*\/(\d+)$/.exec(dayOfMonth);
  if (
    minute === "0" &&
    hour === "0" &&
    dayInterval &&
    month === "*" &&
    dayOfWeek === "*"
  ) {
    return {
      ...fallback,
      schedule_mode: "interval" as ScheduleMode,
      interval_value: Number(dayInterval[1]),
      interval_unit: "days" as IntervalUnit,
    };
  }

  if (hasCronTime && dayOfMonth === "*" && month === "*" && dayOfWeek === "*") {
    return {
      ...fallback,
      schedule_mode: "daily" as ScheduleMode,
      daily_time: time,
    };
  }

  if (
    hasCronTime &&
    dayOfMonth === "*" &&
    month === "*" &&
    Number.isInteger(dayOfWeekNumber) &&
    dayOfWeekNumber >= 0 &&
    dayOfWeekNumber <= 6
  ) {
    return {
      ...fallback,
      schedule_mode: "weekly" as ScheduleMode,
      weekly_day: dayOfWeekNumber,
      weekly_time: time,
    };
  }

  if (
    hasCronTime &&
    Number.isInteger(dayOfMonthNumber) &&
    dayOfMonthNumber >= 1 &&
    dayOfMonthNumber <= 31 &&
    month === "*" &&
    dayOfWeek === "*"
  ) {
    return {
      ...fallback,
      schedule_mode: "monthly" as ScheduleMode,
      monthly_day: dayOfMonthNumber,
      monthly_time: time,
    };
  }

  return fallback;
}

function scheduleTypeClass(mode: string) {
  return `schedule-type--${mode}`;
}

function buildPayload() {
  const runOnce = newJob.value.schedule_mode === "once";
  const cronExpression = runOnce ? "" : buildCronExpression();
  return {
    run_once: runOnce,
    name: newJob.value.name.trim(),
    note: newJob.value.note.trim(),
    cron_expression: cronExpression,
    run_at: runOnce ? toIsoDatetime(newJob.value.run_at) : "",
    session: newJob.value.session,
    timezone: newJob.value.timezone,
    enabled: newJob.value.enabled,
  };
}

function validateJobForm(): boolean {
  if (!newJob.value.name.trim()) {
    toast(tm("messages.nameRequired"), "warning");
    return false;
  }
  if (!newJob.value.note.trim()) {
    toast(tm("messages.noteRequired"), "warning");
    return false;
  }
  return validateScheduleFields();
}

function validateScheduleFields(): boolean {
  const mode = newJob.value.schedule_mode;
  if (mode === "once") {
    if (!newJob.value.run_at) {
      toast(tm("messages.runAtRequired"), "warning");
      return false;
    }
    return true;
  }

  if (mode === "interval") {
    const value = Number(newJob.value.interval_value);
    const validUnit = ["minutes", "hours", "days"].includes(
      newJob.value.interval_unit,
    );
    if (!Number.isInteger(value) || value < 1 || !validUnit) {
      toast(tm("messages.intervalRequired"), "warning");
      return false;
    }
    return true;
  }

  if (mode === "daily") {
    if (!parseTimeParts(newJob.value.daily_time)) {
      toast(tm("messages.dailyTimeRequired"), "warning");
      return false;
    }
    return true;
  }

  if (mode === "weekly") {
    const weekday = Number(newJob.value.weekly_day);
    if (
      !parseTimeParts(newJob.value.weekly_time) ||
      !Number.isInteger(weekday) ||
      weekday < 0 ||
      weekday > 6
    ) {
      toast(tm("messages.weeklyTimeRequired"), "warning");
      return false;
    }
    return true;
  }

  if (mode === "monthly") {
    const day = Number(newJob.value.monthly_day);
    if (
      !parseTimeParts(newJob.value.monthly_time) ||
      !Number.isInteger(day) ||
      day < 1 ||
      day > 31
    ) {
      toast(tm("messages.monthlyTimeRequired"), "warning");
      return false;
    }
    return true;
  }

  if (!newJob.value.cron_expression.trim()) {
    toast(tm("messages.cronRequired"), "warning");
    return false;
  }
  return true;
}

async function createJob() {
  if (!validateJobForm()) {
    return;
  }

  creating.value = true;
  try {
    const payload = buildPayload();
    const res = await cronApi.create(payload);
    if (res.data.status === "ok") {
      toast(tm("messages.createSuccess"));
      createDialog.value = false;
      editingJobId.value = "";
      resetNewJob();
      await loadJobs();
    } else {
      toast(res.data.message || tm("messages.createFailed"), "error");
    }
  } catch (e: any) {
    toast(e?.response?.data?.message || tm("messages.createFailed"), "error");
  } finally {
    creating.value = false;
  }
}

async function updateJob() {
  if (!editingJobId.value) {
    return;
  }
  if (!validateJobForm()) {
    return;
  }

  creating.value = true;
  try {
    const payload = {
      ...buildPayload(),
      description: newJob.value.note,
    };
    const res = await cronApi.update(editingJobId.value, payload);
    if (res.data.status === "ok") {
      toast(tm("messages.updateSuccess"));
      createDialog.value = false;
      editingJobId.value = "";
      resetNewJob();
      await loadJobs();
    } else {
      toast(res.data.message || tm("messages.updateFailed"), "error");
    }
  } catch (e: any) {
    toast(e?.response?.data?.message || tm("messages.updateFailed"), "error");
  } finally {
    creating.value = false;
  }
}

async function submitJob() {
  if (isEditing.value) {
    await updateJob();
    return;
  }
  await createJob();
}

onMounted(() => {
  loadJobs();
  loadPlatforms();
});
</script>

<style scoped>
@import "@/styles/dashboard-shell.css";

.cron-page {
  padding-bottom: 40px;
  background: linear-gradient(
      180deg,
      rgba(var(--v-theme-primary), 0.05),
      transparent 260px
    ),
    rgb(var(--v-theme-background));
}

.cron-shell {
  max-width: 1420px;
  padding: 24px 34px 34px !important;
}

.cron-detail-width {
  width: 100%;
  max-width: none;
  margin: 0 auto;
}

.cron-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 16px !important;
  padding: 0 2px 0 !important;
}

.cron-header-copy {
  min-width: 0;
}

.cron-header-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.cron-header-actions :deep(.v-btn) {
  height: 38px;
  border-radius: 8px;
  font-weight: 650;
  letter-spacing: 0;
}

.task-surface {
  min-width: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.task-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(var(--v-theme-border), 0.52);
  border-radius: 12px;
  background: linear-gradient(
      180deg,
      rgba(255, 255, 255, 0.92),
      rgba(248, 251, 255, 0.86)
    ),
    rgb(var(--v-theme-surface));
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.035);
}

.task-filter-bar :deep(.v-field) {
  min-height: 42px;
  border: 1px solid rgba(var(--v-theme-border), 0.48);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.92) !important;
  box-shadow: none !important;
}

.task-filter-bar :deep(.v-field__input) {
  min-height: 42px;
  padding-top: 8px;
  padding-bottom: 8px;
}

.task-filter-bar :deep(.v-input) {
  flex: 0 1 auto;
}

.task-filter-bar :deep(.v-text-field) {
  width: 280px;
}

.task-filter-bar :deep(.v-autocomplete) {
  width: 340px;
}

.task-bulk-actions {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  padding: 4px 6px 4px 8px;
  border: 1px solid rgba(var(--v-theme-border), 0.42);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.74);
}

.task-select-all,
.task-card-checkbox {
  flex: 0 0 auto;
}

.task-selected-count {
  color: rgba(var(--v-theme-on-surface), 0.64);
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
}

.task-bulk-delete-btn {
  height: 32px !important;
  border-radius: 8px !important;
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0;
}

.supported-platform-link {
  min-width: 0;
  padding-inline: 4px;
  vertical-align: baseline;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 !important;
}

.task-list :deep(.outlined-action-list-item) {
  --task-accent: 56, 143, 196;
  --task-chip-bg: 232, 244, 252;
  --task-chip-text: 35, 111, 159;
  position: relative;
  border: 1px solid rgba(var(--task-accent), 0.16);
  border-radius: 14px !important;
  background: linear-gradient(
      180deg,
      rgba(var(--task-accent), 0.045),
      rgba(255, 255, 255, 0.9) 58%
    ),
    rgb(var(--v-theme-surface));
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
  overflow: hidden;
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.16s ease;
}

.task-list :deep(.outlined-action-list-item::before) {
  content: "";
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 4px;
  border-radius: 999px;
  background: rgba(var(--task-accent), 0.68);
}

.task-list :deep(.outlined-action-list-item:hover) {
  border-color: rgba(var(--task-accent), 0.28);
  background: linear-gradient(
      180deg,
      rgba(var(--task-accent), 0.07),
      rgba(255, 255, 255, 0.94) 62%
    ),
    rgb(var(--v-theme-surface));
  box-shadow: 0 14px 30px rgba(var(--task-accent), 0.1);
  transform: translateY(-1px);
}

.task-list :deep(.outlined-action-list-item.task-item--once) {
  --task-accent: 218, 125, 43;
  --task-chip-bg: 255, 239, 219;
  --task-chip-text: 160, 82, 20;
}

.task-list :deep(.outlined-action-list-item.task-item--interval) {
  --task-accent: 56, 143, 196;
  --task-chip-bg: 232, 244, 252;
  --task-chip-text: 35, 111, 159;
}

.task-list :deep(.outlined-action-list-item.task-item--daily) {
  --task-accent: 22, 151, 132;
  --task-chip-bg: 224, 247, 242;
  --task-chip-text: 19, 111, 98;
}

.task-list :deep(.outlined-action-list-item.task-item--weekly) {
  --task-accent: 105, 91, 210;
  --task-chip-bg: 238, 235, 255;
  --task-chip-text: 82, 69, 170;
}

.task-list :deep(.outlined-action-list-item.task-item--monthly) {
  --task-accent: 201, 88, 140;
  --task-chip-bg: 253, 232, 242;
  --task-chip-text: 157, 62, 108;
}

.task-list :deep(.outlined-action-list-item.task-item--cron) {
  --task-accent: 99, 111, 130;
  --task-chip-bg: 239, 242, 246;
  --task-chip-text: 75, 85, 99;
}

.task-list :deep(.outlined-action-list-item__main) {
  min-height: 84px;
  padding: 13px 16px 13px 18px;
  gap: 18px;
}

.task-list :deep(.outlined-action-list-item__content) {
  flex: 1 1 auto;
  min-width: 0;
}

.task-list :deep(.outlined-action-list-item__title) {
  color: rgba(var(--v-theme-on-surface), 0.92);
  font-size: 15.5px;
  font-weight: 700;
}

.task-list :deep(.outlined-action-list-item__header) {
  gap: 10px;
  margin-bottom: 8px;
}

.task-list :deep(.task-card-checkbox) {
  margin-inline-start: -4px;
}

.task-list :deep(.outlined-action-list-item__actions) {
  min-height: 48px;
  border-left: 1px solid rgba(var(--v-theme-border), 0.46);
  padding: 4px 0 4px 16px;
}

.task-description {
  display: -webkit-box;
  max-width: 920px;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
  color: rgba(var(--v-theme-on-surface), 0.72);
  font-size: 13px;
  line-height: 1.5;
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 8px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 12px;
}

.task-meta-item {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  border: 1px solid rgba(var(--v-theme-border), 0.38);
  border-radius: 999px;
  background: rgba(247, 250, 253, 0.78);
  overflow: hidden;
  padding: 3px 8px;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.task-list :deep(.v-chip) {
  border-radius: 999px;
  font-weight: 650;
}

.task-list :deep(.schedule-type-chip) {
  background: rgb(var(--task-chip-bg)) !important;
  color: rgb(var(--task-chip-text)) !important;
  letter-spacing: 0;
}

.cron-umo-platform {
  margin-inline-start: 12px;
  max-width: 96px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.umo-selection-chip {
  max-width: 100%;
}

.umo-selection-chip :deep(.v-chip__content) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-inline-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-inline-action-btn {
  height: 34px !important;
  border: 1px solid rgba(var(--v-theme-border), 0.46);
  border-radius: 8px !important;
  background: rgba(247, 250, 253, 0.88) !important;
  color: rgba(var(--v-theme-on-surface), 0.72) !important;
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0;
  padding-inline: 10px !important;
}

.task-inline-action-btn:hover {
  border-color: rgba(var(--task-accent), 0.24);
  background: rgba(var(--task-accent), 0.08) !important;
  color: rgb(var(--task-chip-text)) !important;
}

.task-inline-action-btn--edit {
  border-color: rgba(52, 124, 206, 0.18);
  background: rgba(233, 243, 255, 0.9) !important;
  color: #286fae !important;
}

.task-inline-action-btn--edit:hover {
  border-color: rgba(52, 124, 206, 0.32);
  background: rgba(221, 237, 255, 0.96) !important;
  color: #1f5f9b !important;
}

.task-inline-action-btn--run {
  border-color: rgba(31, 151, 111, 0.18);
  background: rgba(228, 247, 240, 0.9) !important;
  color: #17795c !important;
}

.task-inline-action-btn--run:hover {
  border-color: rgba(31, 151, 111, 0.32);
  background: rgba(215, 242, 232, 0.96) !important;
  color: #12684f !important;
}

.task-inline-action-btn--danger {
  border-color: rgba(229, 81, 81, 0.16);
  background: rgba(255, 241, 241, 0.9) !important;
  color: #c33d3d !important;
}

.task-inline-action-btn--danger:hover {
  border-color: rgba(229, 81, 81, 0.3);
  background: rgba(255, 231, 231, 0.95) !important;
  color: #b42323 !important;
}

.task-list :deep(.v-switch .v-selection-control) {
  min-height: 34px;
}

.cron-empty-state {
  display: flex;
  min-height: 190px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px 18px;
  border: 1px solid rgba(var(--v-theme-border), 0.54);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.78);
  color: rgba(var(--v-theme-on-surface), 0.56);
}

.cron-job-dialog-card {
  border: 1px solid rgba(var(--v-theme-border), 0.68);
  border-radius: 16px !important;
  background: linear-gradient(
      180deg,
      rgba(var(--v-theme-primary), 0.035),
      transparent 180px
    ),
    rgb(var(--v-theme-surface));
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.18) !important;
  overflow: hidden;
}

.cron-job-dialog-title {
  position: relative;
  min-height: 62px;
  padding: 20px 24px 16px 30px !important;
  border-bottom: 1px solid rgba(var(--v-theme-border), 0.56);
  background: rgba(255, 255, 255, 0.78);
  color: rgb(var(--v-theme-primaryText));
  font-size: 1.18rem !important;
  font-weight: 720 !important;
  letter-spacing: 0;
}

.cron-job-dialog-title::before {
  content: "";
  position: absolute;
  left: 18px;
  top: 21px;
  bottom: 17px;
  width: 3px;
  border-radius: 999px;
  background: rgb(var(--v-theme-primary));
}

.cron-job-dialog-body {
  max-height: min(76vh, 720px);
  overflow-y: auto;
  padding: 18px 22px 8px !important;
  background: rgba(248, 250, 252, 0.64);
}

.cron-job-dialog-body :deep(.v-field) {
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.94);
}

.cron-job-dialog-body :deep(.v-field__outline) {
  --v-field-border-opacity: 0.18;
}

.cron-job-dialog-body :deep(.v-field--focused .v-field__outline) {
  --v-field-border-opacity: 0.48;
}

.cron-job-dialog-actions {
  gap: 10px;
  padding: 14px 22px 18px !important;
  border-top: 1px solid rgba(var(--v-theme-border), 0.54);
  background: rgba(255, 255, 255, 0.88);
}

.cron-job-primary-btn,
.cron-job-secondary-btn {
  height: 40px !important;
  max-height: 40px;
  border-radius: 8px !important;
  padding: 0 18px;
  font-weight: 650;
  letter-spacing: 0;
}

.cron-job-secondary-btn {
  border: 1px solid rgba(var(--v-theme-border), 0.76);
  background: rgba(255, 255, 255, 0.9);
  color: rgba(var(--v-theme-on-surface), 0.74);
}

.platform-dialog-card {
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-primary), 0.16);
  border-radius: 18px !important;
  background:
    linear-gradient(180deg, rgba(var(--v-theme-primary), 0.055), transparent 150px),
    rgb(var(--v-theme-surface));
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.2) !important;
}

.platform-dialog-title {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 24px 28px 10px !important;
  color: rgb(var(--v-theme-primaryText));
  font-size: 1.28rem !important;
  font-weight: 740;
  line-height: 1.3;
  letter-spacing: 0;
}

.platform-dialog-title__mark {
  width: 4px;
  height: 36px;
  flex: 0 0 auto;
  margin-top: 1px;
  border-radius: 999px;
  background: linear-gradient(
    180deg,
    rgb(var(--v-theme-primary)),
    rgba(var(--v-theme-primary), 0.38)
  );
}

.platform-dialog-title__copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.platform-dialog-title__copy small {
  color: rgba(var(--v-theme-on-surface), 0.56);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.35;
}

.platform-dialog-body {
  padding: 10px 28px 12px !important;
}

.platform-dialog-note {
  margin-bottom: 14px;
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-theme-border), 0.5);
  border-radius: 12px;
  background: rgba(248, 251, 253, 0.72);
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 13px;
  line-height: 1.65;
}

.platform-list {
  display: grid;
  gap: 10px;
}

.platform-list-item {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 13px 14px;
  border: 1px solid rgba(var(--v-theme-primary), 0.14);
  border-radius: 12px;
  background: linear-gradient(
    90deg,
    rgba(var(--v-theme-primary), 0.055),
    rgba(248, 251, 253, 0.88) 48%
  );
  transition:
    border-color 0.16s ease,
    background-color 0.16s ease,
    transform 0.16s ease;
}

.platform-list-item:hover {
  border-color: rgba(var(--v-theme-primary), 0.28);
  background: linear-gradient(
    90deg,
    rgba(var(--v-theme-primary), 0.085),
    rgba(248, 251, 253, 0.94) 48%
  );
  transform: translateY(-1px);
}

.platform-list-item__badge {
  display: inline-flex;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(var(--v-theme-primary), 0.12);
  border-radius: 10px;
  background: rgba(var(--v-theme-primary), 0.09);
  color: rgb(var(--v-theme-primary));
  font-size: 14px;
  font-weight: 740;
}

.platform-list-item__content {
  min-width: 0;
}

.platform-name {
  min-width: 0;
  color: rgb(var(--v-theme-primaryText));
  font-size: 15px;
  font-weight: 760;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.platform-id {
  margin-top: 4px;
  color: rgba(var(--v-theme-on-surface), 0.56);
  font-size: 12px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.platform-list-item__status {
  padding: 5px 9px;
  border: 1px solid rgba(var(--v-theme-primary), 0.13);
  border-radius: 999px;
  background: rgba(var(--v-theme-primary), 0.09);
  color: rgb(var(--v-theme-primary));
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.platform-dialog-empty {
  min-height: 120px;
  border: 1px dashed rgba(var(--v-theme-border), 0.72);
  border-radius: 12px;
  background: rgba(248, 251, 253, 0.7);
}

.platform-dialog-actions {
  gap: 10px;
  padding: 4px 28px 24px !important;
}

.platform-dialog-close-btn {
  min-width: 92px;
  height: 40px !important;
  max-height: 40px;
  border: 1px solid rgba(var(--v-theme-primary), 0.14);
  border-radius: 8px !important;
  font-weight: 650;
  letter-spacing: 0;
}

.schedule-field {
  display: grid;
  grid-template-columns: minmax(150px, 180px) minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  margin-bottom: 16px;
}

.schedule-mode-select {
  --schedule-accent: 56, 143, 196;
  min-width: 0;
}

.schedule-mode-select :deep(.v-field) {
  border-color: rgba(var(--schedule-accent), 0.22);
  background: rgba(var(--schedule-accent), 0.035);
}

.schedule-mode-selection {
  --schedule-accent: 56, 143, 196;
  --schedule-text: 35, 111, 159;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: rgb(var(--schedule-text));
  font-weight: 650;
}

.schedule-mode-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border-radius: 999px;
  background: rgb(var(--schedule-accent));
  box-shadow: 0 0 0 4px rgba(var(--schedule-accent), 0.1);
}

.schedule-type--once {
  --schedule-accent: 218, 125, 43;
  --schedule-text: 160, 82, 20;
}

.schedule-type--interval {
  --schedule-accent: 56, 143, 196;
  --schedule-text: 35, 111, 159;
}

.schedule-type--daily {
  --schedule-accent: 22, 151, 132;
  --schedule-text: 19, 111, 98;
}

.schedule-type--weekly {
  --schedule-accent: 105, 91, 210;
  --schedule-text: 82, 69, 170;
}

.schedule-type--monthly {
  --schedule-accent: 201, 88, 140;
  --schedule-text: 157, 62, 108;
}

.schedule-type--cron {
  --schedule-accent: 99, 111, 130;
  --schedule-text: 75, 85, 99;
}

.schedule-inline-fields {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
}

@media (max-width: 900px) {
  .cron-header {
    align-items: stretch;
    flex-direction: column;
  }

  .cron-header-actions {
    justify-content: flex-start;
  }

  .task-filter-bar {
    align-items: stretch;
  }

  .task-bulk-actions {
    width: 100%;
    margin-left: 0;
  }

  .schedule-field,
  .schedule-inline-fields {
    grid-template-columns: 1fr;
  }
}
</style>

<style>
.cron-umo-menu .cron-umo-platform {
  border: 1px solid rgba(56, 143, 196, 0.16) !important;
  background: rgba(239, 247, 252, 0.94) !important;
  color: #2d6f9f !important;
  font-weight: 650;
}

.cron-umo-menu .v-list-item:hover {
  background: rgba(56, 143, 196, 0.045) !important;
}

.schedule-mode-menu .schedule-mode-option {
  --schedule-accent: 56, 143, 196;
  --schedule-text: 35, 111, 159;
  margin: 4px 6px;
  border-radius: 8px;
  color: rgba(31, 41, 55, 0.86);
}

.schedule-mode-menu .schedule-mode-option .v-list-item__prepend {
  width: 24px;
}

.schedule-mode-menu .schedule-mode-option:hover,
.schedule-mode-menu .schedule-mode-option.v-list-item--active {
  background: rgba(var(--schedule-accent), 0.09) !important;
  color: rgb(var(--schedule-text)) !important;
}

.schedule-mode-menu .schedule-type--once {
  --schedule-accent: 218, 125, 43;
  --schedule-text: 160, 82, 20;
}

.schedule-mode-menu .schedule-type--interval {
  --schedule-accent: 56, 143, 196;
  --schedule-text: 35, 111, 159;
}

.schedule-mode-menu .schedule-type--daily {
  --schedule-accent: 22, 151, 132;
  --schedule-text: 19, 111, 98;
}

.schedule-mode-menu .schedule-type--weekly {
  --schedule-accent: 105, 91, 210;
  --schedule-text: 82, 69, 170;
}

.schedule-mode-menu .schedule-type--monthly {
  --schedule-accent: 201, 88, 140;
  --schedule-text: 157, 62, 108;
}

.schedule-mode-menu .schedule-type--cron {
  --schedule-accent: 99, 111, 130;
  --schedule-text: 75, 85, 99;
}

.schedule-mode-menu .schedule-mode-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgb(var(--schedule-accent));
  box-shadow: 0 0 0 4px rgba(var(--schedule-accent), 0.1);
}
</style>
