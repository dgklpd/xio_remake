<script setup lang="ts">
import { onLaunch, onShow, onHide } from "@dcloudio/uni-app";
onLaunch(() => {
  console.log("Xu Miniapp Launch");
});
onShow(() => {
  console.log("Xu Miniapp Show");
});
onHide(() => {
  console.log("Xu Miniapp Hide");
});
</script>
<style lang="scss">
page {
  background:
    radial-gradient(circle at top, rgba(233, 196, 106, 0.14), transparent 30%),
    linear-gradient(180deg, #09141d 0%, #102433 48%, #0b1720 100%);
  color: #f5efe2;
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
}

view,
text,
button {
  box-sizing: border-box;
}

button::after {
  border: none;
}
</style>
