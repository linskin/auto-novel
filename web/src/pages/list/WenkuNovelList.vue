<script lang="ts" setup>
import {
  ApiWenkuNovel,
  WenkuNovelOutlineDto,
} from '@/data/api/api_wenku_novel';
import { Page } from '@/data/api/common';
import { useUserDataStore } from '@/data/stores/user_data';

import { Loader } from './components/NovelList.vue';

const userData = useUserDataStore();

const options = userData.isOldAss
  ? [
      {
        label: '分级',
        tags: ['一般向', 'R18'],
      },
    ]
  : [];

const loader: Loader<Page<WenkuNovelOutlineDto>> = (page, query, selected) => {
  if (userData.isOldAss) {
    return ApiWenkuNovel.listNovel({
      page,
      pageSize: 24,
      query,
      level: selected[0] + 1,
    });
  } else {
    return ApiWenkuNovel.listNovel({
      page,
      pageSize: 24,
      query,
      level: 1,
    });
  }
};
</script>

<template>
  <MainLayout>
    <n-h1>文库小说</n-h1>
    <RouterNA to="/wenku-edit">新建文库小说</RouterNA>
    <NovelList
      :search="true"
      :options="options"
      :loader="loader"
      v-slot="{ page }"
    >
      <NovelListWenku :items="page.items" />
    </NovelList>
  </MainLayout>
</template>

<style scoped>
.n-card-header__main {
  text-overflow: ellipsis;
}
</style>
