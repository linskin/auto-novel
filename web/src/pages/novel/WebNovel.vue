<script lang="ts" setup>
import { ref } from 'vue';
import { useRoute } from 'vue-router';
import { EditNoteFilled, BookFilled, SortFilled } from '@vicons/material';
import { createReusableTemplate } from '@vueuse/core';

import { Ok, ResultState } from '@/data/result';
import {
  ApiWebNovel,
  WebNovelDto,
  WebNovelTocItemDto,
} from '@/data/api/api_web_novel';
import { buildWebNovelUrl, tryTranslateKeyword } from '@/data/util_web';
import { useSettingStore } from '@/data/stores/setting';

const [DefineTag, ReuseTag] = createReusableTemplate<{
  tag: string;
  attention: boolean;
}>();

const setting = useSettingStore();

const route = useRoute();
const providerId = route.params.providerId as string;
const novelId = route.params.novelId as string;

const novelResult = ref<ResultState<WebNovelDto>>();

async function getNovel() {
  novelResult.value = undefined;
  const result = await ApiWebNovel.getNovel(providerId, novelId);
  novelResult.value = result;
  if (result.ok) {
    document.title = result.value.titleJp;
  }
}
getNovel();

const editMode = ref(false);
</script>

<template>
  <DefineTag v-slot="{ tag, attention }">
    <router-link
      :to="`/novel-list?query=${tag}\$`"
      style="color: rgb(51, 54, 57)"
    >
      <n-tag :bordered="false" size="small">
        <template v-if="attention">
          <b>{{ tag }}</b>
        </template>
        <template v-else>
          {{ tryTranslateKeyword(tag) }}
        </template>
      </n-tag>
    </router-link>
  </DefineTag>

  <MainLayout>
    <ResultView
      :result="novelResult"
      :showEmpty="() => false"
      v-slot="{ value: novel }"
    >
      <n-h1 prefix="bar" style="font-size: 22px">
        <n-a :href="buildWebNovelUrl(providerId, novelId)">{{
          novel.titleJp
        }}</n-a>
        <br />
        <n-text depth="3">{{ novel.titleZh }}</n-text>
      </n-h1>

      <n-p v-if="novel.authors.length > 0">
        作者：
        <template v-for="author in novel.authors">
          <n-a :href="author.link">{{ author.name }}</n-a>
        </template>
      </n-p>

      <n-space>
        <async-button @async-click="async () => (editMode = !editMode)">
          <template #icon>
            <n-icon :component="EditNoteFilled" />
          </template>
          {{ editMode ? '退出编辑' : '编辑' }}
        </async-button>

        <favorite-button
          :favored="novel.favored"
          :favored-list="novel.favoredList"
          :novel="{ type: 'web', providerId, novelId }"
          @update:favored="getNovel"
        />

        <router-link v-if="novel.wenkuId" :to="`/wenku/${novel.wenkuId}`">
          <n-button>
            <template #icon>
              <n-icon :component="BookFilled" />
            </template>
            文库
          </n-button>
        </router-link>
      </n-space>

      <WebEdit
        v-if="editMode"
        :provider-id="providerId"
        :novel-id="novelId"
        :novel-metadata="novel"
        @update:novel-metadata="novelResult = Ok(novel)"
      />

      <template v-else>
        <n-p>{{ novel.type }} / 浏览次数:{{ novel.visited }}</n-p>

        <n-p style="word-break: break-all">
          {{ novel.introductionJp }}
        </n-p>
        <n-p
          v-if="novel.introductionZh !== undefined"
          style="word-break: break-all"
        >
          {{ novel.introductionZh }}
        </n-p>

        <n-space :size="[4, 4]">
          <ReuseTag
            v-for="attention of novel.attentions.sort()"
            :tag="attention"
            :attention="true"
          />
          <ReuseTag
            v-for="keyword of novel.keywords"
            :tag="keyword"
            :attention="false"
          />
        </n-space>

        <section>
          <SectionHeader title="翻译" />
          <WebTranslate
            :provider-id="providerId"
            :novel-id="novelId"
            :title-jp="novel.titleJp"
            :title-zh="novel.titleZh"
            :total="novel.toc.filter((it: WebNovelTocItemDto) => it.chapterId).length"
            v-model:jp="novel.jp"
            v-model:baidu="novel.baidu"
            v-model:youdao="novel.youdao"
            v-model:gpt="novel.gpt"
            :sakura="novel.sakura"
            :glossary="novel.glossary"
          />
        </section>

        <section>
          <SectionHeader title="目录">
            <n-button @click="setting.tocSortReverse = !setting.tocSortReverse">
              <template #icon>
                <n-icon :component="SortFilled" />
              </template>
              {{ setting.tocSortReverse ? '倒序' : '正序' }}
            </n-button>
          </SectionHeader>
          <SectionWebToc
            :provider-id="providerId"
            :novel-id="novelId"
            :toc="novel.toc"
            :reverse="setting.tocSortReverse"
            :last-read-chapter-id="novel.lastReadChapterId"
          />
        </section>

        <CommentList :site="`web-${providerId}-${novelId}`" />
      </template>
    </ResultView>
  </MainLayout>
</template>
